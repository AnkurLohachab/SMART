"""SMART lineage helpers (SMARTNameRegistry + SMARTVersionRegistry)."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from web3 import Web3

logger = logging.getLogger(__name__)


RELATION_NAMES = ["Patch", "Recalibration", "Retrain", "Reformulation", "Reindication", "Withdrawal"]
ENVELOPE_STATUS_NAMES = ["Asserted", "Disputed", "Upheld", "Repudiated"]


_WEB3_PROVIDER_URL = os.getenv("WEB3_PROVIDER_URL", "http://hardhat:8545")
_w3 = Web3(Web3.HTTPProvider(_WEB3_PROVIDER_URL))


def _load_addresses() -> Dict[str, Any]:
    try:
        with open("/deployments/addresses.json", "r") as fh:
            return json.load(fh)["contracts"]
    except Exception as exc:
        logger.warning("lineage: could not load deployment addresses: %s", exc)
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


def _name_addr() -> str:
    a = _ADDRS.get("core", {}).get("SMARTNameRegistry") or os.getenv("SMART_NAME_REGISTRY_ADDRESS")
    if not a:
        raise RuntimeError("SMARTNameRegistry address not configured")
    return Web3.to_checksum_address(a)


def _version_addr() -> str:
    a = _ADDRS.get("core", {}).get("SMARTVersionRegistry") or os.getenv("SMART_VERSION_REGISTRY_ADDRESS")
    if not a:
        raise RuntimeError("SMARTVersionRegistry address not configured")
    return Web3.to_checksum_address(a)


def _name_reg():
    return _w3.eth.contract(address=_name_addr(), abi=_load_abi("SMARTNameRegistry"))


def _version_reg():
    return _w3.eth.contract(address=_version_addr(), abi=_load_abi("SMARTVersionRegistry"))




def _decode_version_record(raw) -> Dict[str, Any]:
    """Decode a tuple from versionOf(tokenId) into a dict."""
    relation_idx = int(raw[3])
    status_idx = int(raw[6])
    return {
        "token_id": int(raw[0]),
        "name_hash": raw[1].hex() if isinstance(raw[1], (bytes, bytearray)) else str(raw[1]),
        "supersedes": int(raw[2]),
        "relation": RELATION_NAMES[relation_idx] if 0 <= relation_idx < len(RELATION_NAMES) else str(relation_idx),
        "relation_index": relation_idx,
        "envelope_hash": raw[4].hex() if isinstance(raw[4], (bytes, bytearray)) else str(raw[4]),
        "within_envelope": bool(raw[5]),
        "envelope_status": ENVELOPE_STATUS_NAMES[status_idx] if 0 <= status_idx < len(ENVELOPE_STATUS_NAMES) else str(status_idx),
        "envelope_status_index": status_idx,
        "minted_at": int(raw[7]),
        "minted_by": raw[8],
        "challenger": raw[9],
        "challenged_at": int(raw[10]),
        "arbiter": raw[11],
        "resolved_at": int(raw[12]),
    }


def _decode_envelope(raw) -> Dict[str, Any]:
    return {
        "hash": raw[0].hex() if isinstance(raw[0], (bytes, bytearray)) else str(raw[0]),
        "pinned_at": int(raw[1]),
        "updated_at": int(raw[2]),
        "pinned_by": raw[3],
    }




def _name_hash(name: str) -> bytes:
    return Web3.keccak(text=name)


def get_version(token_id: int) -> Dict[str, Any]:
    """Return the on-chain VersionRecord for a tokenId (token_id=0 means no lineage on file)."""
    rec = _version_reg().functions.versionOf(int(token_id)).call()
    return _decode_version_record(rec)


def get_line(name: str) -> Dict[str, Any]:
    """Return name record, envelope, and decoded version list for a line, by name."""
    name_str = (name or "").strip()
    if not name_str:
        raise ValueError("name is required")

    nh = _name_hash(name_str)
    name_reg = _name_reg()
    version_reg = _version_reg()

    name_record = name_reg.functions.records(nh).call()
    alias_bytes = name_reg.functions.aliasOf(name_str).call()
    has_name = bool(alias_bytes) and len(alias_bytes) > 0

    env = _decode_envelope(version_reg.functions.envelopeFor(nh).call())

    token_ids = version_reg.functions.lineageOf(nh).call()
    versions = []
    for tid in token_ids:
        try:
            versions.append(_decode_version_record(version_reg.functions.versionOf(int(tid)).call()))
        except Exception as exc:
            logger.debug("lineage: failed to decode version %s: %s", tid, exc)

    return {
        "name": name_str,
        "name_hash": nh.hex(),
        "alias": alias_bytes.hex() if isinstance(alias_bytes, (bytes, bytearray)) else str(alias_bytes),
        "has_name_record": has_name,
        "controller": name_record[2] if has_name else None,
        "first_claimed_at": int(name_record[3]) if has_name else 0,
        "envelope": env,
        "versions": versions,
    }


def list_disputed_versions(limit: int = 200) -> List[Dict[str, Any]]:
    """Return versions currently in Disputed state."""
    version_reg = _version_reg()
    total = int(version_reg.functions.totalVersions().call())
    out: List[Dict[str, Any]] = []
    for tid in range(total, 0, -1):
        if len(out) >= limit:
            break
        try:
            rec = _decode_version_record(version_reg.functions.versionOf(tid).call())
        except Exception:
            continue
        if rec["envelope_status"] == "Disputed":
            out.append(rec)
    return out



_RELAYER_PRIVATE_KEY = os.getenv("RELAYER_PRIVATE_KEY") or os.getenv("PRIVATE_KEY") or ""
_relayer_account = _w3.eth.account.from_key(_RELAYER_PRIVATE_KEY) if _RELAYER_PRIVATE_KEY else None


def challenge_version(token_id: int, reason: str) -> Dict[str, Any]:
    fn = _version_reg().functions.challengeEnvelope(int(token_id), reason or "")
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


def resolve_version(token_id: int, final_status: str) -> Dict[str, Any]:
    if final_status not in ("Upheld", "Repudiated"):
        raise ValueError("final_status must be Upheld or Repudiated")
    final_idx = ENVELOPE_STATUS_NAMES.index(final_status)
    fn = _version_reg().functions.resolveEnvelope(int(token_id), final_idx)
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
