"""Blockchain utilities for the model card lifecycle via the gasless relayer."""

import json
import logging
import hashlib
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct
from typing import Dict, Any
import os

logger = logging.getLogger(__name__)

def load_contract_addresses():
    try:
        with open("/deployments/addresses.json", "r") as f:
            deployment = json.load(f)
            return deployment["contracts"]
    except Exception as e:
        logger.warning(f"Could not load deployment addresses: {e}")
        return {}

CONTRACTS = load_contract_addresses()

WEB3_PROVIDER_URL = os.getenv("WEB3_PROVIDER_URL", "http://hardhat:8545")
w3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER_URL))

def compute_content_hash(content: str) -> bytes:
    """Return the SHA-256 hash of content as bytes32."""
    return hashlib.sha256(content.encode('utf-8')).digest()


MLUCE_RELAYER_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "creator", "type": "address"},
            {"internalType": "string", "name": "metadataURI", "type": "string"},
            {"internalType": "bytes32", "name": "contentHash", "type": "bytes32"},
            {"internalType": "bytes", "name": "signature", "type": "bytes"}
        ],
        "name": "relayCreateModelCard",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "address", "name": "initiator", "type": "address"},
            {"internalType": "bytes", "name": "signature", "type": "bytes"}
        ],
        "name": "relaySubmitForEvaluation",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "address", "name": "validator", "type": "address"},
            {"internalType": "bytes", "name": "signature", "type": "bytes"}
        ],
        "name": "relayValidateModelCard",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "address", "name": "rejector", "type": "address"},
            {"internalType": "string", "name": "reason", "type": "string"},
            {"internalType": "bytes", "name": "signature", "type": "bytes"}
        ],
        "name": "relayRejectModelCard",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "address", "name": "requester", "type": "address"},
            {"internalType": "string", "name": "feedback", "type": "string"},
            {"internalType": "bytes", "name": "signature", "type": "bytes"}
        ],
        "name": "relayRequestRevision",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "address", "name": "revisor", "type": "address"},
            {"internalType": "string", "name": "newMetadataURI", "type": "string"},
            {"internalType": "bytes32", "name": "newContentHash", "type": "bytes32"},
            {"internalType": "string", "name": "revisionNotes", "type": "string"},
            {"internalType": "bytes", "name": "signature", "type": "bytes"}
        ],
        "name": "relayReviseModelCard",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "address", "name": "publisher", "type": "address"},
            {"internalType": "bytes", "name": "signature", "type": "bytes"}
        ],
        "name": "relayPublishModelCard",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "address", "name": "deprecator", "type": "address"},
            {"internalType": "string", "name": "reason", "type": "string"},
            {"internalType": "bytes", "name": "signature", "type": "bytes"}
        ],
        "name": "relayDeprecateModelCard",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "getNonce",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

MLUCE_ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "getModelCard",
        "outputs": [
            {
                "components": [
                    {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                    {"internalType": "address", "name": "creator", "type": "address"},
                    {"internalType": "string", "name": "metadataURI", "type": "string"},
                    {"internalType": "bytes32", "name": "contentHash", "type": "bytes32"},
                    {"internalType": "uint8", "name": "status", "type": "uint8"},
                    {"internalType": "uint256", "name": "createdAt", "type": "uint256"},
                    {"internalType": "uint256", "name": "lastUpdated", "type": "uint256"},
                    {"internalType": "string", "name": "revisionNotes", "type": "string"},
                    {"internalType": "address", "name": "lastModifiedBy", "type": "address"},
                    {"internalType": "bool", "name": "isActive", "type": "bool"}
                ],
                "internalType": "struct MLUCE.ModelCard",
                "name": "",
                "type": "tuple"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "getContentHash",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "bytes32", "name": "providedHash", "type": "bytes32"}
        ],
        "name": "verifyContentIntegrity",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    }
]

def _resolve_address(json_keys, env_keys, label):
    """Resolve a contract address from /deployments/addresses.json or env vars."""
    for section, key in json_keys:
        addr = CONTRACTS.get(section, {}).get(key)
        if addr:
            return addr
    for var in env_keys:
        addr = os.getenv(var)
        if addr:
            return addr
    raise Exception(f"{label} address not found")


def get_relayer_contract():
    address = _resolve_address(
        json_keys=[
            ("core", "SMARTRelayer"),
            ("core", "SMARTLifecycleRelayer"),
            ("core", "SimpleGaslessRelayer"),
            ("account", "SimpleGaslessRelayer"),
        ],
        env_keys=[
            "SMART_RELAYER_ADDRESS",
            "SMART_LIFECYCLE_RELAYER_ADDRESS",
            "MLUCE_GASLESS_RELAYER_ADDRESS",
            "GASLESS_RELAYER_ADDRESS",
            "SIMPLE_GASLESS_RELAYER_ADDRESS",
        ],
        label="lifecycle relayer",
    )
    logger.info(f"Using lifecycle relayer at: {address}")
    return w3.eth.contract(address=address, abi=MLUCE_RELAYER_ABI)


def get_mluce_contract():
    address = _resolve_address(
        json_keys=[
            ("core", "SMARTLifecycle"),
            ("core", "MLUCE"),
        ],
        env_keys=[
            "SMART_LIFECYCLE_ADDRESS",
            "MLUCE_ADDRESS",
        ],
        label="lifecycle contract",
    )
    return w3.eth.contract(address=address, abi=MLUCE_ABI)

RELAYER_PRIVATE_KEY = os.getenv("RELAYER_PRIVATE_KEY", "")
relayer_account = Account.from_key(RELAYER_PRIVATE_KEY) if RELAYER_PRIVATE_KEY else None

# Local-dev signer keys, supplied via env as JSON {"address": "private_key"}.
# For local Hardhat, use the accounts printed by `npx hardhat node`.
HARDHAT_TEST_ACCOUNTS = json.loads(os.getenv("HARDHAT_TEST_ACCOUNTS", "{}"))

SMART_ACCOUNT_TO_SIGNER = {}

def load_smart_account_mappings():
    """Load smart account to signer mappings from deployment addresses"""
    global SMART_ACCOUNT_TO_SIGNER
    try:
        with open("/deployments/addresses.json", "r") as f:
            deployment = json.load(f)
            test_accounts = deployment.get("testAccounts", {})
            for role, data in test_accounts.items():
                smart_account = data.get("account")
                signer = data.get("signer")
                if smart_account and signer:
                    SMART_ACCOUNT_TO_SIGNER[Web3.to_checksum_address(smart_account)] = Web3.to_checksum_address(signer)
                    SMART_ACCOUNT_TO_SIGNER[smart_account.lower()] = Web3.to_checksum_address(signer)
                    logger.info(f"Mapped smart account {smart_account} -> signer {signer}")
    except Exception as e:
        logger.warning(f"Could not load smart account mappings: {e}")

load_smart_account_mappings()

def get_private_key_for_address(address: str) -> str:
    """Get the private key for a hardhat test address (sync version for backwards compatibility)"""
    checksum_address = Web3.to_checksum_address(address)
    return HARDHAT_TEST_ACCOUNTS.get(checksum_address, RELAYER_PRIVATE_KEY)

async def get_private_key_for_user(address: str) -> str:
    """Get the private key for a user address (EOA or smart account)."""
    from app.db import neo4j_conn

    checksum_address = Web3.to_checksum_address(address)
    logger.debug(f"Looking up private key for address: {checksum_address}")

    if checksum_address in HARDHAT_TEST_ACCOUNTS:
        logger.debug(f"Found EOA in hardhat test accounts: {checksum_address}")
        return HARDHAT_TEST_ACCOUNTS[checksum_address]

    if checksum_address in SMART_ACCOUNT_TO_SIGNER:
        signer_address = SMART_ACCOUNT_TO_SIGNER[checksum_address]
        logger.debug(f"Smart account {checksum_address} -> signer {signer_address}")
        if signer_address in HARDHAT_TEST_ACCOUNTS:
            logger.debug(f"Found signer in hardhat test accounts")
            return HARDHAT_TEST_ACCOUNTS[signer_address]

    private_key = await neo4j_conn.get_private_key_by_address(checksum_address)
    if private_key:
        return private_key

    logger.warning(f"No private key found for address {checksum_address}, using relayer key")
    return RELAYER_PRIVATE_KEY

import threading as _threading

_relayer_nonce_cache: Dict[str, int] = {}
_relayer_nonce_lock = _threading.Lock()


def _refetch_relayer_nonce(checksum_address: str) -> int:
    relayer = get_relayer_contract()
    return int(relayer.functions.getNonce(checksum_address).call())


async def get_nonce(user_address: str) -> int:
    """Get the next per-user relayer nonce from the local cache, refetching from chain on miss."""
    checksum_address = Web3.to_checksum_address(user_address)
    with _relayer_nonce_lock:
        n = _relayer_nonce_cache.get(checksum_address)
        if n is None:
            n = _refetch_relayer_nonce(checksum_address)
            _relayer_nonce_cache[checksum_address] = n
        return n


def bump_relayer_nonce(user_address: str) -> None:
    """Advance the cached nonce after a relayed tx is mined."""
    checksum_address = Web3.to_checksum_address(user_address)
    with _relayer_nonce_lock:
        _relayer_nonce_cache[checksum_address] = _relayer_nonce_cache.get(checksum_address, 0) + 1


def invalidate_relayer_nonce(user_address: str) -> None:
    """Drop the cached nonce so the next call refetches from chain."""
    checksum_address = Web3.to_checksum_address(user_address)
    with _relayer_nonce_lock:
        _relayer_nonce_cache.pop(checksum_address, None)

def sign_message(user_private_key: str, message_hash: bytes) -> str:
    """Sign a message hash"""
    account = Account.from_key(user_private_key)
    message = encode_defunct(hexstr=message_hash.hex())
    signed = account.sign_message(message)
    return signed.signature.hex()

async def create_model_card_on_chain(
    creator: str,
    metadata_uri: str,
    metadata_json: str = None,
    content_hash: bytes = None,
    user_private_key: str = None
) -> Dict[str, Any]:
    """Create a model card via the gasless relayer with a content hash."""
    try:
        relayer = get_relayer_contract()

        signer_address = await get_signer_address_async(creator)
        logger.info(f"Create model card - Original: {creator}, Signer: {signer_address}")

        nonce = await get_nonce(signer_address)

        if content_hash is None:
            if metadata_json is None:
                raise ValueError("Either metadata_json or content_hash must be provided")
            content_hash = compute_content_hash(metadata_json)

        message_hash = w3.solidity_keccak(
            ['address', 'string', 'bytes32', 'uint256'],
            [signer_address, metadata_uri, content_hash, nonce]
        )

        if not user_private_key:
            user_private_key = await get_private_key_for_user(creator)

        signature = sign_message(user_private_key, message_hash)

        tx = relayer.functions.relayCreateModelCard(
            signer_address,
            metadata_uri,
            content_hash,
            bytes.fromhex(signature[2:])
        ).build_transaction({
            'from': relayer_account.address,
            'nonce': w3.eth.get_transaction_count(relayer_account.address, 'pending'),
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, RELAYER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        try:
            if receipt.get('status') == 1:
                bump_relayer_nonce(signer_address)
            else:
                invalidate_relayer_nonce(signer_address)
        except NameError:
            pass

        def _norm_sig(s):
            if isinstance(s, (bytes, bytearray)):
                s = s.hex()
            return s.lower().removeprefix("0x")

        relayer_event_signature = _norm_sig(w3.keccak(text="RelayedCreateModelCard(uint256,address)"))

        token_id = None
        for log in receipt['logs']:
            try:
                if len(log['topics']) > 0:
                    event_sig = _norm_sig(log['topics'][0])
                    if event_sig == relayer_event_signature:
                        token_id_bytes = log['topics'][1] if isinstance(log['topics'][1], bytes) else bytes.fromhex(log['topics'][1].replace('0x', ''))
                        token_id = int.from_bytes(token_id_bytes, byteorder='big')
                        logger.info(f"Found RelayedCreateModelCard event, token_id: {token_id}")
                        break
            except Exception as e:
                logger.warning(f"Error parsing log: {e}")
                continue

        if token_id is None:
            nft_minted_signature = _norm_sig(w3.keccak(text="NFTMinted(uint256,address,string,bytes32,uint256)"))
            for log in receipt['logs']:
                try:
                    if len(log['topics']) > 0:
                        event_sig = _norm_sig(log['topics'][0])
                        if event_sig == nft_minted_signature:
                            token_id_bytes = log['topics'][1] if isinstance(log['topics'][1], bytes) else bytes.fromhex(log['topics'][1].replace('0x', ''))
                            token_id = int.from_bytes(token_id_bytes, byteorder='big')
                            logger.info(f"Found NFTMinted event, token_id: {token_id}")
                            break
                except Exception as e:
                    logger.warning(f"Error parsing NFTMinted log: {e}")
                    continue

        content_hash_hex = '0x' + content_hash.hex()
        logger.info(f"Model card created on-chain. Token ID: {token_id}, TX: {tx_hash.hex()}, ContentHash: {content_hash_hex}")

        return {
            "token_id": token_id,
            "tx_hash": tx_hash.hex(),
            "content_hash": content_hash_hex,
            "block_number": receipt['blockNumber']
        }

    except Exception as e:
        logger.error(f"Failed to create model card on-chain: {str(e)}")
        raise

def get_signer_address(address: str) -> str:
    """Get the EOA signer address for a given address (sync, deployment mappings only)."""
    checksum_address = Web3.to_checksum_address(address)

    if checksum_address in SMART_ACCOUNT_TO_SIGNER:
        signer = SMART_ACCOUNT_TO_SIGNER[checksum_address]
        logger.info(f"Resolved smart account {checksum_address} to signer {signer}")
        return signer

    return checksum_address


async def get_signer_address_async(address: str) -> str:
    """Get the EOA signer address, checking deployment mappings then Neo4j, falling back to the address."""
    from app.db import neo4j_conn

    logger.info(f"get_signer_address_async called with address: {address}")
    checksum_address = Web3.to_checksum_address(address)
    logger.info(f"Checksum address: {checksum_address}")

    if checksum_address in SMART_ACCOUNT_TO_SIGNER:
        signer = SMART_ACCOUNT_TO_SIGNER[checksum_address]
        logger.info(f"Resolved smart account {checksum_address} to signer {signer} (from deployment)")
        return signer

    logger.info(f"Address not in deployment mappings, checking Neo4j...")

    try:
        query = """
        MATCH (u:User)-[:HAS_CUSTOM_ACCOUNT]->(ca:CustomAccount)
        WHERE ca.address = $address OR ca.address = toLower($address)
              OR ca.address = $checksum_address
        RETURN u.eoa_address AS eoa_address
        """
        logger.info(f"Executing Neo4j query for address: {address}")
        result = await neo4j_conn.query(query, {
            "address": address,
            "checksum_address": checksum_address
        })
        logger.info(f"Neo4j query result: {result}")

        if result and len(result) > 0 and result[0].get("eoa_address"):
            eoa = Web3.to_checksum_address(result[0].get("eoa_address"))
            logger.info(f"Resolved smart account {checksum_address} to signer {eoa} (from Neo4j)")
            return eoa
        else:
            logger.warning(f"No EOA found in Neo4j for address {checksum_address}")
    except Exception as e:
        logger.error(f"Failed to lookup signer from Neo4j: {e}", exc_info=True)

    logger.info(f"Address {checksum_address} assumed to be EOA (fallback)")
    return checksum_address


async def submit_for_evaluation(
    token_id: int,
    initiator: str,
    user_private_key: str = None
) -> Dict[str, Any]:
    """Submit model card for evaluation"""
    try:
        relayer = get_relayer_contract()

        signer_address = await get_signer_address_async(initiator)
        logger.info(f"Submit for evaluation - Original: {initiator}, Signer: {signer_address}")

        nonce = await get_nonce(signer_address)

        message_hash = w3.solidity_keccak(
            ['uint256', 'address', 'uint256'],
            [token_id, signer_address, nonce]
        )

        if not user_private_key:
            user_private_key = await get_private_key_for_user(initiator)

        signature = sign_message(user_private_key, message_hash)

        tx = relayer.functions.relaySubmitForEvaluation(
            token_id,
            signer_address,
            bytes.fromhex(signature[2:])
        ).build_transaction({
            'from': relayer_account.address,
            'nonce': w3.eth.get_transaction_count(relayer_account.address, 'pending'),
            'gas': 3_000_000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, RELAYER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        try:
            if receipt.get('status') == 1:
                bump_relayer_nonce(signer_address)
            else:
                invalidate_relayer_nonce(signer_address)
        except NameError:
            pass

        return {"tx_hash": tx_hash.hex(), "block_number": receipt['blockNumber']}

    except Exception as e:
        logger.error(f"Failed to submit for evaluation: {str(e)}")
        raise

async def validate_model_card(
    token_id: int,
    validator: str,
    user_private_key: str = None
) -> Dict[str, Any]:
    """Validate model card"""
    try:
        relayer = get_relayer_contract()

        signer_address = await get_signer_address_async(validator)
        logger.info(f"Validate model card - Original: {validator}, Signer: {signer_address}")

        nonce = await get_nonce(signer_address)

        message_hash = w3.solidity_keccak(
            ['uint256', 'address', 'uint256'],
            [token_id, signer_address, nonce]
        )

        if not user_private_key:
            user_private_key = await get_private_key_for_user(validator)

        signature = sign_message(user_private_key, message_hash)

        tx = relayer.functions.relayValidateModelCard(
            token_id,
            signer_address,
            bytes.fromhex(signature[2:])
        ).build_transaction({
            'from': relayer_account.address,
            'nonce': w3.eth.get_transaction_count(relayer_account.address, 'pending'),
            'gas': 3_000_000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, RELAYER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        try:
            if receipt.get('status') == 1:
                bump_relayer_nonce(signer_address)
            else:
                invalidate_relayer_nonce(signer_address)
        except NameError:
            pass

        return {"tx_hash": tx_hash.hex(), "block_number": receipt['blockNumber']}

    except Exception as e:
        logger.error(f"Failed to validate model card: {str(e)}")
        raise

async def reject_model_card(
    token_id: int,
    rejector: str,
    reason: str,
    user_private_key: str = None
) -> Dict[str, Any]:
    """Reject model card"""
    try:
        relayer = get_relayer_contract()

        signer_address = await get_signer_address_async(rejector)
        logger.info(f"Reject model card - Original: {rejector}, Signer: {signer_address}")

        nonce = await get_nonce(signer_address)

        message_hash = w3.solidity_keccak(
            ['uint256', 'address', 'string', 'uint256'],
            [token_id, signer_address, reason, nonce]
        )

        if not user_private_key:
            user_private_key = await get_private_key_for_user(rejector)

        signature = sign_message(user_private_key, message_hash)

        tx = relayer.functions.relayRejectModelCard(
            token_id,
            signer_address,
            reason,
            bytes.fromhex(signature[2:])
        ).build_transaction({
            'from': relayer_account.address,
            'nonce': w3.eth.get_transaction_count(relayer_account.address, 'pending'),
            'gas': 3_000_000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, RELAYER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        try:
            if receipt.get('status') == 1:
                bump_relayer_nonce(signer_address)
            else:
                invalidate_relayer_nonce(signer_address)
        except NameError:
            pass

        return {"tx_hash": tx_hash.hex(), "block_number": receipt['blockNumber']}

    except Exception as e:
        logger.error(f"Failed to reject model card: {str(e)}")
        raise

async def request_revision(
    token_id: int,
    requester: str,
    feedback: str,
    user_private_key: str = None
) -> Dict[str, Any]:
    """Request revision for model card"""
    try:
        relayer = get_relayer_contract()

        signer_address = await get_signer_address_async(requester)
        logger.info(f"Request revision - Original: {requester}, Signer: {signer_address}")

        nonce = await get_nonce(signer_address)

        message_hash = w3.solidity_keccak(
            ['uint256', 'address', 'string', 'uint256'],
            [token_id, signer_address, feedback, nonce]
        )

        if not user_private_key:
            user_private_key = await get_private_key_for_user(requester)

        signature = sign_message(user_private_key, message_hash)

        tx = relayer.functions.relayRequestRevision(
            token_id,
            signer_address,
            feedback,
            bytes.fromhex(signature[2:])
        ).build_transaction({
            'from': relayer_account.address,
            'nonce': w3.eth.get_transaction_count(relayer_account.address, 'pending'),
            'gas': 3_000_000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, RELAYER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        try:
            if receipt.get('status') == 1:
                bump_relayer_nonce(signer_address)
            else:
                invalidate_relayer_nonce(signer_address)
        except NameError:
            pass

        return {"tx_hash": tx_hash.hex(), "block_number": receipt['blockNumber']}

    except Exception as e:
        logger.error(f"Failed to request revision: {str(e)}")
        raise

async def revise_model_card(
    token_id: int,
    revisor: str,
    new_metadata_uri: str,
    revision_notes: str,
    metadata_json: str = None,
    content_hash: bytes = None,
    user_private_key: str = None
) -> Dict[str, Any]:
    """Revise model card with content hash for integrity verification"""
    try:
        relayer = get_relayer_contract()

        signer_address = await get_signer_address_async(revisor)
        logger.info(f"Revise model card - Original: {revisor}, Signer: {signer_address}")

        if content_hash is None:
            if metadata_json is None:
                content_hash = b'\x00' * 32
            else:
                content_hash = compute_content_hash(metadata_json)

        nonce = await get_nonce(signer_address)

        message_hash = w3.solidity_keccak(
            ['uint256', 'address', 'string', 'bytes32', 'string', 'uint256'],
            [token_id, signer_address, new_metadata_uri, content_hash, revision_notes, nonce]
        )

        if not user_private_key:
            user_private_key = await get_private_key_for_user(revisor)

        signature = sign_message(user_private_key, message_hash)

        tx = relayer.functions.relayReviseModelCard(
            token_id,
            signer_address,
            new_metadata_uri,
            content_hash,
            revision_notes,
            bytes.fromhex(signature[2:])
        ).build_transaction({
            'from': relayer_account.address,
            'nonce': w3.eth.get_transaction_count(relayer_account.address, 'pending'),
            'gas': 3_000_000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, RELAYER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        try:
            if receipt.get('status') == 1:
                bump_relayer_nonce(signer_address)
            else:
                invalidate_relayer_nonce(signer_address)
        except NameError:
            pass

        content_hash_hex = '0x' + content_hash.hex()
        return {"tx_hash": tx_hash.hex(), "block_number": receipt['blockNumber'], "content_hash": content_hash_hex}

    except Exception as e:
        logger.error(f"Failed to revise model card: {str(e)}")
        raise

async def publish_model_card(
    token_id: int,
    publisher: str,
    user_private_key: str = None
) -> Dict[str, Any]:
    """Publish model card"""
    try:
        relayer = get_relayer_contract()

        signer_address = await get_signer_address_async(publisher)
        logger.info(f"Publish model card - Original: {publisher}, Signer: {signer_address}")

        nonce = await get_nonce(signer_address)

        message_hash = w3.solidity_keccak(
            ['uint256', 'address', 'uint256'],
            [token_id, signer_address, nonce]
        )

        if not user_private_key:
            user_private_key = await get_private_key_for_user(publisher)

        signature = sign_message(user_private_key, message_hash)

        tx = relayer.functions.relayPublishModelCard(
            token_id,
            signer_address,
            bytes.fromhex(signature[2:])
        ).build_transaction({
            'from': relayer_account.address,
            'nonce': w3.eth.get_transaction_count(relayer_account.address, 'pending'),
            'gas': 3_000_000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, RELAYER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        try:
            if receipt.get('status') == 1:
                bump_relayer_nonce(signer_address)
            else:
                invalidate_relayer_nonce(signer_address)
        except NameError:
            pass

        return {"tx_hash": tx_hash.hex(), "block_number": receipt['blockNumber']}

    except Exception as e:
        logger.error(f"Failed to publish model card: {str(e)}")
        raise

async def deprecate_model_card(
    token_id: int,
    deprecator: str,
    reason: str,
    user_private_key: str = None
) -> Dict[str, Any]:
    """Deprecate model card"""
    try:
        relayer = get_relayer_contract()

        signer_address = await get_signer_address_async(deprecator)
        logger.info(f"Deprecate model card - Original: {deprecator}, Signer: {signer_address}")

        nonce = await get_nonce(signer_address)

        message_hash = w3.solidity_keccak(
            ['uint256', 'address', 'string', 'uint256'],
            [token_id, signer_address, reason, nonce]
        )

        if not user_private_key:
            user_private_key = await get_private_key_for_user(deprecator)

        signature = sign_message(user_private_key, message_hash)

        tx = relayer.functions.relayDeprecateModelCard(
            token_id,
            signer_address,
            reason,
            bytes.fromhex(signature[2:])
        ).build_transaction({
            'from': relayer_account.address,
            'nonce': w3.eth.get_transaction_count(relayer_account.address, 'pending'),
            'gas': 3_000_000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, RELAYER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        try:
            if receipt.get('status') == 1:
                bump_relayer_nonce(signer_address)
            else:
                invalidate_relayer_nonce(signer_address)
        except NameError:
            pass

        return {"tx_hash": tx_hash.hex(), "block_number": receipt['blockNumber']}

    except Exception as e:
        logger.error(f"Failed to deprecate model card: {str(e)}")
        raise

async def get_model_card_from_chain(token_id: int) -> Dict[str, Any]:
    """Get model card data from blockchain including content hash"""
    try:
        mluce = get_mluce_contract()
        card = mluce.functions.getModelCard(token_id).call()

        STATUS_MAP = {
            0: "Created",
            1: "InEvaluation",
            2: "Validated",
            3: "Rejected",
            4: "RevisionRequested",
            5: "Revised",
            6: "Published",
            7: "Deprecated"
        }

        content_hash = card[3]
        content_hash_hex = '0x' + content_hash.hex() if content_hash else None

        return {
            "token_id": card[0],
            "creator": card[1],
            "metadata_uri": card[2],
            "content_hash": content_hash_hex,
            "status": STATUS_MAP.get(card[4], "Unknown"),
            "created_at": card[5],
            "last_updated": card[6],
            "revision_notes": card[7],
            "last_modified_by": card[8],
            "is_active": card[9]
        }

    except Exception as e:
        logger.error(f"Failed to get model card from chain: {str(e)}")
        raise


async def verify_content_integrity(token_id: int, metadata_json: str) -> Dict[str, Any]:
    """Verify that the metadata content matches the on-chain hash."""
    try:
        mluce = get_mluce_contract()

        computed_hash = compute_content_hash(metadata_json)

        on_chain_hash = mluce.functions.getContentHash(token_id).call()

        is_valid = computed_hash == on_chain_hash

        return {
            "token_id": token_id,
            "is_valid": is_valid,
            "computed_hash": '0x' + computed_hash.hex(),
            "on_chain_hash": '0x' + on_chain_hash.hex(),
            "message": "Content integrity verified - metadata is authentic" if is_valid
                      else "Content integrity failed - metadata may have been tampered with"
        }

    except Exception as e:
        logger.error(f"Failed to verify content integrity: {str(e)}")
        raise


async def get_content_hash_from_chain(token_id: int) -> str:
    """Get the content hash for a model card from blockchain"""
    try:
        mluce = get_mluce_contract()
        content_hash = mluce.functions.getContentHash(token_id).call()
        return '0x' + content_hash.hex()

    except Exception as e:
        logger.error(f"Failed to get content hash from chain: {str(e)}")
        raise



_LINEAGE_RELAYER_ABI = [
    {
        "inputs": [
            {"internalType": "string",  "name": "name",          "type": "string"},
            {"internalType": "bytes32", "name": "envelopeHash",   "type": "bytes32"},
            {"internalType": "address", "name": "controller",     "type": "address"},
            {"internalType": "bytes",   "name": "signature",      "type": "bytes"},
        ],
        "name": "relayPinLineEnvelope",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "creator",        "type": "address"},
            {"internalType": "string",  "name": "name",           "type": "string"},
            {"internalType": "string",  "name": "metadataURI",    "type": "string"},
            {"internalType": "bytes32", "name": "contentHash",    "type": "bytes32"},
            {"internalType": "uint256", "name": "supersedes",     "type": "uint256"},
            {"internalType": "uint8",   "name": "relation",       "type": "uint8"},
            {"internalType": "bool",    "name": "withinEnvelope", "type": "bool"},
            {"internalType": "bytes",   "name": "signature",      "type": "bytes"},
        ],
        "name": "relayCreateModelCardWithLineage",
        "outputs": [
            {"internalType": "uint256", "name": "tokenId",  "type": "uint256"},
            {"internalType": "bytes",   "name": "aliasOut", "type": "bytes"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


def _lineage_relayer():
    """Relayer instance with the lineage-method ABI subset."""
    address = get_relayer_contract().address
    return w3.eth.contract(address=address, abi=_LINEAGE_RELAYER_ABI)


async def pin_line_envelope_on_chain(
    name: str,
    envelope_hash: bytes,
    controller: str,
    user_private_key: str = None,
) -> Dict[str, Any]:
    """Pin a predetermined-change envelope hash for a line."""
    relayer = _lineage_relayer()
    signer_address = await get_signer_address_async(controller)
    nonce = await get_nonce(signer_address)

    message_hash = w3.solidity_keccak(
        ["string", "bytes32", "address", "uint256"],
        [name, envelope_hash, signer_address, nonce],
    )
    if not user_private_key:
        user_private_key = await get_private_key_for_user(controller)
    signature = sign_message(user_private_key, message_hash)

    tx = relayer.functions.relayPinLineEnvelope(
        name, envelope_hash, signer_address, bytes.fromhex(signature[2:])
    ).build_transaction({
        "from": relayer_account.address,
        "nonce": w3.eth.get_transaction_count(relayer_account.address, 'pending'),
        "gas": 500_000,
        "gasPrice": w3.eth.gas_price,
    })
    signed = w3.eth.account.sign_transaction(tx, RELAYER_PRIVATE_KEY)
    raw = signed.rawTransaction if hasattr(signed, "rawTransaction") else signed.raw_transaction
    tx_hash = w3.eth.send_raw_transaction(raw)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    try:
        if receipt.get("status") == 1:
            bump_relayer_nonce(signer_address)
        else:
            invalidate_relayer_nonce(signer_address)
    except NameError:
        pass
    return {"tx_hash": tx_hash.hex(), "block_number": receipt["blockNumber"]}


async def create_model_card_with_lineage_on_chain(
    creator: str,
    name: str,
    metadata_uri: str,
    content_hash: bytes,
    supersedes: int,
    relation: int,
    within_envelope: bool,
    user_private_key: str = None,
) -> Dict[str, Any]:
    """Mint a model card and record it as a version under a named line (relation = Relation enum index)."""
    relayer = _lineage_relayer()
    signer_address = await get_signer_address_async(creator)
    nonce = await get_nonce(signer_address)

    message_hash = w3.solidity_keccak(
        ["address", "string", "string", "bytes32", "uint256", "uint8", "bool", "uint256"],
        [signer_address, name, metadata_uri, content_hash,
         int(supersedes), int(relation), bool(within_envelope), nonce],
    )
    if not user_private_key:
        user_private_key = await get_private_key_for_user(creator)
    signature = sign_message(user_private_key, message_hash)

    tx = relayer.functions.relayCreateModelCardWithLineage(
        signer_address,
        name,
        metadata_uri,
        content_hash,
        int(supersedes),
        int(relation),
        bool(within_envelope),
        bytes.fromhex(signature[2:]),
    ).build_transaction({
        "from": relayer_account.address,
        "nonce": w3.eth.get_transaction_count(relayer_account.address, 'pending'),
        "gas": 3_000_000,
        "gasPrice": w3.eth.gas_price,
    })
    signed = w3.eth.account.sign_transaction(tx, RELAYER_PRIVATE_KEY)
    raw = signed.rawTransaction if hasattr(signed, "rawTransaction") else signed.raw_transaction
    tx_hash = w3.eth.send_raw_transaction(raw)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    relayer_event_sig = w3.keccak(text="RelayedCreateModelCard(uint256,address)").hex()
    token_id = None
    for log in receipt["logs"]:
        if log["address"].lower() == relayer.address.lower() and log["topics"]:
            t0 = log["topics"][0].hex() if hasattr(log["topics"][0], "hex") else log["topics"][0]
            if t0 == relayer_event_sig:
                tid_hex = log["topics"][1].hex() if hasattr(log["topics"][1], "hex") else log["topics"][1]
                token_id = int(tid_hex, 16)
                break

    return {
        "tx_hash": tx_hash.hex(),
        "block_number": receipt["blockNumber"],
        "token_id": token_id,
    }
