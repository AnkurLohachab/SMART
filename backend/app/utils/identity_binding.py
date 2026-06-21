"""Identity binding read/write helpers."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from web3 import Web3
from eth_account.messages import encode_defunct

logger = logging.getLogger(__name__)


STATUS_NAMES = [
    "Created",
    "InEvaluation",
    "Validated",
    "Rejected",
    "RevisionRequested",
    "Revised",
    "Published",
    "Deprecated",
]

TRANSITION_NAMES = [
    "Create",
    "Submit",
    "Validate",
    "Reject",
    "RequestRevision",
    "Revise",
    "Publish",
    "Deprecate",
    "AdminPublish",
    "AdminDeprecate",
]

IDENTITY_STATUS_NAMES = [
    "Bound",
    "UnboundOptimistic",
    "UnboundMissing",
    "Disputed",
    "ResolvedValid",
    "ResolvedInvalid",
]

REPUDIATION_REASONS = [
    "NoClaim",
    "ExpiredClaim",
    "RevokedClaim",
    "InvalidIssuer",
    "SubjectMismatch",
    "ContextMismatch",
    "SignatureInvalid",
    "RegistryInconsistency",
]

CLAIM_TYPE_NAMES = {
    1: "AI Developer",
    2: "Reviewer",
    3: "Publisher",
    4: "Institution",
    5: "Certification",
}

ROLE_TO_CLAIM_TYPES = {
    "AIDeveloper": [1],
    "Reviewer": [2],
    "Publisher": [3],
    "Admin": [1, 3],
    "Reader": [],
    "Authenticator": [2],
}

ATTESTATION_LEVELS = ("self", "institutional")

HIGH_STAKES_TO_STATES = {2, 6}



_WEB3_PROVIDER_URL = os.getenv("WEB3_PROVIDER_URL", "http://hardhat:8545")
_w3 = Web3(Web3.HTTPProvider(_WEB3_PROVIDER_URL))


def _load_addresses() -> Dict[str, Any]:
    try:
        with open("/deployments/addresses.json", "r") as fh:
            return json.load(fh)["contracts"]
    except Exception as exc:
        logger.warning("Could not load deployment addresses: %s", exc)
        return {}


def _load_abi(name: str) -> list:
    here = os.path.dirname(__file__)
    with open(os.path.join(here, "abis", f"{name}.json"), "r") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "abi" in data:
        return data["abi"]
    raise ValueError(f"Invalid ABI shape for {name}")


_ADDRS = _load_addresses()


def _lifecycle_addr() -> str:
    addr = _ADDRS.get("core", {}).get("SMARTLifecycle") or os.getenv("SMART_LIFECYCLE_ADDRESS")
    if not addr:
        raise RuntimeError("SMARTLifecycle address not configured")
    return Web3.to_checksum_address(addr)


def _registry_addr() -> str:
    addr = _ADDRS.get("core", {}).get("SMARTIdentityRegistry") or os.getenv(
        "SMART_IDENTITY_REGISTRY_ADDRESS"
    )
    if not addr:
        raise RuntimeError("SMARTIdentityRegistry address not configured")
    return Web3.to_checksum_address(addr)


def _lifecycle():
    return _w3.eth.contract(address=_lifecycle_addr(), abi=_load_abi("SMARTLifecycle"))


def _registry():
    return _w3.eth.contract(address=_registry_addr(), abi=_load_abi("SMARTIdentityRegistry"))




def _decode_action(raw) -> Dict[str, Any]:
    """Decode a getAction(actionId) tuple into a dict."""
    out = {
        "action_id": int(raw[0]),
        "token_id": int(raw[1]),
        "actor": raw[2],
        "from_state": STATUS_NAMES[raw[3]] if raw[3] < len(STATUS_NAMES) else str(raw[3]),
        "to_state": STATUS_NAMES[raw[4]] if raw[4] < len(STATUS_NAMES) else str(raw[4]),
        "to_state_index": int(raw[4]),
        "transition": TRANSITION_NAMES[raw[5]] if raw[5] < len(TRANSITION_NAMES) else str(raw[5]),
        "transition_index": int(raw[5]),
        "content_hash": raw[6].hex() if isinstance(raw[6], (bytes, bytearray)) else str(raw[6]),
        "claim_ref": raw[7].hex() if isinstance(raw[7], (bytes, bytearray)) else str(raw[7]),
        "issuer_ref": raw[8].hex() if isinstance(raw[8], (bytes, bytearray)) else str(raw[8]),
        "context_ref": raw[9].hex() if isinstance(raw[9], (bytes, bytearray)) else str(raw[9]),
        "timestamp": int(raw[10]),
        "block_number": int(raw[11]),
        "registry_version": int(raw[12]),
        "identity_status": IDENTITY_STATUS_NAMES[raw[13]]
        if raw[13] < len(IDENTITY_STATUS_NAMES)
        else str(raw[13]),
        "identity_status_index": int(raw[13]),
        "challenge_reason": REPUDIATION_REASONS[raw[14]]
        if raw[14] < len(REPUDIATION_REASONS)
        else str(raw[14]),
        "arbiter": raw[15],
    }
    if len(raw) > 16:
        out["panel_member_1"] = raw[16]
        out["panel_member_2"] = raw[17]
    if len(raw) > 18:
        out["challenger_onchain"] = raw[18]
    return out


def get_actions_for_token(token_id: int) -> List[Dict[str, Any]]:
    lc = _lifecycle()
    action_ids = lc.functions.getActionsForToken(token_id).call()
    out: List[Dict[str, Any]] = []
    for aid in action_ids:
        out.append(_decode_action(lc.functions.getAction(aid).call()))
    return out


def _attestation_level_for_claim_ref(actor: str, claim_ref_hex: str) -> str:
    """Return the attestation level of the claim matching the action's claim_ref."""
    if not claim_ref_hex or claim_ref_hex == "0" * 64:
        return "none"
    try:
        actor_cs = Web3.to_checksum_address(actor)
    except Exception:
        return "self"
    reg = _registry()
    try:
        claim_ids = reg.functions.getClaimIds(actor_cs).call()
    except Exception:
        return "self"
    for cid in claim_ids:
        try:
            ctype, issuer, sig, data, _uri, issued_at, expires_at, _revoked = (
                reg.functions.getClaim(actor_cs, cid).call()
            )
            content_hash = Web3.solidity_keccak(
                ["address", "uint256", "address", "bytes", "bytes", "uint256", "uint256"],
                [actor_cs, int(ctype), issuer, data, sig, int(issued_at), int(expires_at)],
            ).hex()
            if content_hash.lstrip("0x") == claim_ref_hex.lstrip("0x"):
                decoded = _decode_claim_data(data)
                return decoded.get("attestation_level", "self")
        except Exception:
            continue
    return "self"


def get_governance(token_id: int) -> Dict[str, Any]:
    """Compose the user-facing governance state for a model card."""
    lc = _lifecycle()
    actions = get_actions_for_token(token_id)
    invalid_count, highest_repudiated = lc.functions.getGovernance(token_id).call()

    for a in actions:
        if a["identity_status"] == "Bound":
            a["claim_attestation_level"] = _attestation_level_for_claim_ref(
                a["actor"], a["claim_ref"]
            )
        else:
            a["claim_attestation_level"] = "none"

    bound = sum(1 for a in actions if a["identity_status"] == "Bound")
    disputed = sum(1 for a in actions if a["identity_status"] == "Disputed")
    invalid = sum(1 for a in actions if a["identity_status"] == "ResolvedInvalid")
    unbound = sum(
        1 for a in actions
        if a["identity_status"] in ("UnboundMissing", "UnboundOptimistic")
    )
    self_attested = sum(
        1 for a in actions
        if a["identity_status"] == "Bound" and a["claim_attestation_level"] == "self"
    )

    if not actions:
        state = "no_history"
        reason = (
            "No on-chain actions have been recorded for this card. The card may pre-date "
            "the identity-binding rollout, or no transitions have occurred yet."
        )
    elif invalid > 0:
        state = "compromised"
        target = [a for a in actions if a["identity_status"] == "ResolvedInvalid"][-1]
        reason = (
            f"The identity claim for the {target['transition']} step (action #{target['action_id']}) "
            f"was invalidated by an arbiter."
        )
    elif disputed > 0:
        state = "review"
        target = [a for a in actions if a["identity_status"] == "Disputed"][-1]
        reason = (
            f"The {target['transition']} step (action #{target['action_id']}) is under review "
            f"following a challenge. Awaiting arbiter resolution."
        )
    elif unbound > 0:
        state = "unbound"
        reason = (
            f"{unbound} of {len(actions)} actions were performed by addresses without an "
            f"active identity claim. Lifecycle history is intact; institutional attribution "
            f"is unverified for those steps."
        )
    elif self_attested > 0:
        state = "self_attested"
        reason = (
            f"All {bound} actions are bound to identity claims, but {self_attested} relied on "
            f"self-attested credentials. Institutional verification is pending."
        )
    else:
        state = "clean"
        reason = None

    return {
        "state": state,
        "reason": reason,
        "actions": actions,
        "bound_count": bound,
        "disputed_count": disputed,
        "invalid_count": int(invalid_count),
        "invalid_count_from_actions": invalid,
        "unbound_count": unbound,
        "self_attested_count": self_attested,
        "highest_repudiated_to_state": (
            STATUS_NAMES[highest_repudiated] if int(highest_repudiated) > 0 else None
        ),
        "latest_action_id": actions[-1]["action_id"] if actions else None,
    }


def _decode_claim_data(raw: bytes | bytearray | str) -> Dict[str, Any]:
    """Best-effort decode of the claim's data field; always returns a dict with attestation_level."""
    if not raw:
        return {"attestation_level": "self", "_raw": ""}
    if isinstance(raw, str):
        if raw.startswith("0x"):
            try:
                raw = bytes.fromhex(raw[2:])
            except ValueError:
                return {"attestation_level": "self", "_raw": raw}
        else:
            raw = raw.encode("utf-8", errors="replace")
    try:
        text = bytes(raw).decode("utf-8", errors="replace")
    except Exception:
        return {"attestation_level": "self", "_raw": ""}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            level = "self" if parsed.get("self_attested") else "institutional"
            parsed["attestation_level"] = level
            return parsed
    except Exception:
        pass
    return {"attestation_level": "self", "_raw": text}


def _find_active_claim_id(actor: str, claim_type: int) -> Optional[bytes]:
    """Return the claimId of the actor's newest valid claim of claim_type, or None."""
    actor = Web3.to_checksum_address(actor)
    reg = _registry()
    type_ids = reg.functions.getClaimsByType(actor, claim_type).call()
    if not type_ids:
        return None
    now = int(_w3.eth.get_block("latest")["timestamp"])
    for cid in reversed(type_ids):
        ctype, issuer, _sig, _data, _uri, _issued_at, expires_at, revoked = (
            reg.functions.getClaim(actor, cid).call()
        )
        if issuer == "0x0000000000000000000000000000000000000000":
            continue
        if revoked:
            continue
        if expires_at and now > int(expires_at):
            continue
        try:
            issuer_tuple = reg.functions.getIssuer(issuer).call()
            if not bool(issuer_tuple[0]):
                continue
        except Exception:
            continue
        return cid
    return None


def get_claim_status(actor: str, claim_type: int) -> Dict[str, Any]:
    """Resolve the actor's current best claim of claim_type into a summary dict."""
    actor = Web3.to_checksum_address(actor)
    reg = _registry()
    snap = reg.functions.snapshotOf(actor, claim_type).call()
    claim_ref, issuer_ref, _subject_ref, _ctx_ref, valid_from, valid_until, registry_version = snap

    has_claim = claim_ref != b"\x00" * 32
    issuer_addr: Optional[str] = None
    issuer_name: Optional[str] = None
    issuer_active: Optional[bool] = None
    attestation_level = "self"
    institution: Optional[str] = None
    if has_claim:
        issuer_addr = Web3.to_checksum_address("0x" + issuer_ref.hex()[-40:])
        try:
            issuer_tuple = reg.functions.getIssuer(issuer_addr).call()
            issuer_active = bool(issuer_tuple[0])
            issuer_name = issuer_tuple[1] or None
        except Exception as exc:
            logger.debug("getIssuer failed for %s: %s", issuer_addr, exc)
        cid = _find_active_claim_id(actor, claim_type)
        if cid:
            try:
                _ctype, _iss, _sig, data, _uri, _issued, _expires, _revoked = (
                    reg.functions.getClaim(actor, cid).call()
                )
                decoded = _decode_claim_data(data)
                attestation_level = decoded.get("attestation_level", "self")
                institution = decoded.get("institution") or None
            except Exception as exc:
                logger.debug("getClaim data decode failed: %s", exc)

    attestation_label = (
        "Self-attested"
        if attestation_level == "self"
        else "Institutional"
        if has_claim
        else "-"
    )

    return {
        "actor": actor,
        "claim_type": claim_type,
        "claim_type_name": CLAIM_TYPE_NAMES.get(claim_type, str(claim_type)),
        "has_claim": has_claim,
        "claim_ref": claim_ref.hex() if isinstance(claim_ref, (bytes, bytearray)) else claim_ref,
        "issuer_address": issuer_addr,
        "issuer_name": issuer_name,
        "issuer_active": issuer_active,
        "valid_from": int(valid_from) if valid_from else None,
        "valid_until": int(valid_until) if valid_until else None,
        "registry_version": int(registry_version),
        "attestation_level": attestation_level,
        "attestation_label": attestation_label,
        "institution": institution,
    }


def issue_claim(
    actor: str,
    claim_type: int,
    *,
    self_attested: bool,
    role: Optional[str] = None,
    institution: Optional[str] = None,
    valid_until: int = 0,
) -> Dict[str, Any]:
    """Issue a claim signed by the platform deployer key."""
    actor = Web3.to_checksum_address(actor)
    payload: Dict[str, Any] = {
        "self_attested": bool(self_attested),
    }
    if role:
        payload["role"] = role
    if institution:
        payload["institution"] = institution
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    reg = _registry()
    message_hash = Web3.solidity_keccak(
        ["address", "uint256", "bytes", "uint256"],
        [actor, claim_type, data, int(valid_until)],
    )
    signed = _w3.eth.account.sign_message(
        encode_defunct(message_hash),
        private_key=_RELAYER_PRIVATE_KEY,
    )
    signature = signed.signature

    fn = reg.functions.addClaim(actor, claim_type, data, "", int(valid_until), signature)
    tx = fn.build_transaction({
        "from": _relayer_account.address,
        "nonce": _w3.eth.get_transaction_count(_relayer_account.address, 'pending'),
        "gas": 500_000,
        "gasPrice": _w3.eth.gas_price,
    })
    raw_signed = _w3.eth.account.sign_transaction(tx, _RELAYER_PRIVATE_KEY)
    raw = raw_signed.rawTransaction if hasattr(raw_signed, "rawTransaction") else raw_signed.raw_transaction
    tx_hash = _w3.eth.send_raw_transaction(raw)
    receipt = _w3.eth.wait_for_transaction_receipt(tx_hash)
    return {
        "tx_hash": tx_hash.hex(),
        "block_number": receipt["blockNumber"],
        "actor": actor,
        "claim_type": claim_type,
        "attestation_level": "self" if self_attested else "institutional",
    }


def issue_self_attested_claims_for_role(actor: str, role: str) -> List[Dict[str, Any]]:
    """Issue the self-attested claims a freshly-registered user needs for their role."""
    out = []
    for ct in ROLE_TO_CLAIM_TYPES.get(role, []):
        try:
            out.append(
                issue_claim(actor, ct, self_attested=True, role=role)
            )
        except Exception as exc:
            logger.error("issue_self_attested_claim(%s, %s) failed: %s", actor, ct, exc)
            out.append({"actor": actor, "claim_type": ct, "error": str(exc)})
    return out


def list_disputed_actions(limit: int = 200) -> List[Dict[str, Any]]:
    """Return all currently-Disputed actions across all tokens."""
    lc = _lifecycle()
    next_id = lc.functions.nextActionId().call()
    out: List[Dict[str, Any]] = []
    for aid in range(int(next_id), 0, -1):
        if len(out) >= limit:
            break
        try:
            action = _decode_action(lc.functions.getAction(aid).call())
        except Exception as exc:
            logger.debug("getAction(%s) failed: %s", aid, exc)
            continue
        if action["identity_status"] == "Disputed":
            out.append(action)
    return out


def list_actions_for_actor(actor: str, statuses: Optional[List[str]] = None,
                           limit: int = 200) -> List[Dict[str, Any]]:
    """Return action records performed by actor, optionally filtered by identity_status."""
    actor = Web3.to_checksum_address(actor)
    lc = _lifecycle()
    next_id = int(lc.functions.nextActionId().call())
    out: List[Dict[str, Any]] = []
    for aid in range(next_id, 0, -1):
        if len(out) >= limit:
            break
        try:
            action = _decode_action(lc.functions.getAction(aid).call())
        except Exception:
            continue
        if Web3.to_checksum_address(action["actor"]) != actor:
            continue
        if statuses and action["identity_status"] not in statuses:
            continue
        out.append(action)
    return out



_RELAYER_PRIVATE_KEY = os.getenv("RELAYER_PRIVATE_KEY") or os.getenv("PRIVATE_KEY") or ""
_relayer_account = _w3.eth.account.from_key(_RELAYER_PRIVATE_KEY) if _RELAYER_PRIVATE_KEY else None


def challenge_action(action_id: int, reason: str, challenger: Optional[str] = None) -> Dict[str, Any]:
    """Mark an on-chain action as Disputed."""
    if reason not in REPUDIATION_REASONS:
        raise ValueError(f"Unknown repudiation reason: {reason}")
    reason_idx = REPUDIATION_REASONS.index(reason)
    challenger_addr = Web3.to_checksum_address(challenger) if challenger else _relayer_account.address
    lc = _lifecycle()
    fn = lc.functions.challengeAction(action_id, reason_idx, challenger_addr)
    tx = fn.build_transaction({
        "from": _relayer_account.address,
        "nonce": _w3.eth.get_transaction_count(_relayer_account.address, 'pending'),
        "gas": 300_000,
        "gasPrice": _w3.eth.gas_price,
    })
    signed = _w3.eth.account.sign_transaction(tx, _RELAYER_PRIVATE_KEY)
    raw = signed.rawTransaction if hasattr(signed, "rawTransaction") else signed.raw_transaction
    tx_hash = _w3.eth.send_raw_transaction(raw)
    receipt = _w3.eth.wait_for_transaction_receipt(tx_hash)
    return {"tx_hash": tx_hash.hex(), "block_number": receipt["blockNumber"]}


def resolve_dispute(action_id: int, final_status: str) -> Dict[str, Any]:
    if final_status not in ("ResolvedValid", "ResolvedInvalid"):
        raise ValueError("final_status must be ResolvedValid or ResolvedInvalid")
    final_idx = IDENTITY_STATUS_NAMES.index(final_status)
    lc = _lifecycle()
    fn = lc.functions.resolveDispute(action_id, final_idx)
    tx = fn.build_transaction({
        "from": _relayer_account.address,
        "nonce": _w3.eth.get_transaction_count(_relayer_account.address, 'pending'),
        "gas": 300_000,
        "gasPrice": _w3.eth.gas_price,
    })
    signed = _w3.eth.account.sign_transaction(tx, _RELAYER_PRIVATE_KEY)
    raw = signed.rawTransaction if hasattr(signed, "rawTransaction") else signed.raw_transaction
    tx_hash = _w3.eth.send_raw_transaction(raw)
    receipt = _w3.eth.wait_for_transaction_receipt(tx_hash)
    return {"tx_hash": tx_hash.hex(), "block_number": receipt["blockNumber"]}


def resolve_dispute_quorum(
    action_id: int,
    final_status: str,
    signer1: str,
    sig1_hex: str,
    signer2: str,
    sig2_hex: str,
) -> Dict[str, Any]:
    """Submit a 2-of-N panel resolution."""
    if final_status not in ("ResolvedValid", "ResolvedInvalid"):
        raise ValueError("final_status must be ResolvedValid or ResolvedInvalid")
    final_idx = IDENTITY_STATUS_NAMES.index(final_status)
    sig1 = bytes.fromhex(sig1_hex[2:] if sig1_hex.startswith("0x") else sig1_hex)
    sig2 = bytes.fromhex(sig2_hex[2:] if sig2_hex.startswith("0x") else sig2_hex)

    lc = _lifecycle()
    fn = lc.functions.resolveDisputeQuorum(
        int(action_id),
        final_idx,
        Web3.to_checksum_address(signer1),
        sig1,
        Web3.to_checksum_address(signer2),
        sig2,
    )
    tx = fn.build_transaction({
        "from": _relayer_account.address,
        "nonce": _w3.eth.get_transaction_count(_relayer_account.address, 'pending'),
        "gas": 500_000,
        "gasPrice": _w3.eth.gas_price,
    })
    signed = _w3.eth.account.sign_transaction(tx, _RELAYER_PRIVATE_KEY)
    raw = signed.rawTransaction if hasattr(signed, "rawTransaction") else signed.raw_transaction
    tx_hash = _w3.eth.send_raw_transaction(raw)
    receipt = _w3.eth.wait_for_transaction_receipt(tx_hash)
    return {"tx_hash": tx_hash.hex(), "block_number": receipt["blockNumber"]}


def panel_vote_digest(action_id: int, final_status: str) -> str:
    """Return the canonical panel-vote digest as a hex string."""
    if final_status not in ("ResolvedValid", "ResolvedInvalid"):
        raise ValueError("final_status must be ResolvedValid or ResolvedInvalid")
    final_idx = IDENTITY_STATUS_NAMES.index(final_status)
    lc = _lifecycle()
    return lc.functions.panelVoteDigest(int(action_id), final_idx).call().hex()
