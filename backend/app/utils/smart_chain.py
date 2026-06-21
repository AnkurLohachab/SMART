
import os
import json
import asyncio
import logging
from web3 import Web3
from eth_account import Account
from eth_utils import to_checksum_address, is_address
from fastapi import HTTPException
from web3.exceptions import ContractLogicError, MismatchedABI
from eth_account.messages import encode_defunct
from hexbytes import HexBytes
from typing import Dict, Optional

from app.config import settings
from app.db import neo4j_conn
from app.utils.eip712_utils import eip712_encode_hash

logger = logging.getLogger("smart_chain")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)


class SMARTChainManager:
    """Blockchain operations against the SMART factory, relayer, and lifecycle contracts."""

    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(settings.INFURA_URL))
        if not self.w3.is_connected():
            logger.error("Web3 is not connected. Check your provider URI.")
            raise ConnectionError("Web3 is not connected. Check your provider URI.")
        logger.info("Web3 connected successfully.")

        self.factory_contract_address = to_checksum_address(settings.SMART_ACCOUNT_FACTORY_ADDRESS)
        self.factory_contract = self.w3.eth.contract(
            address=self.factory_contract_address,
            abi=self.load_factory_abi()
        )
        logger.info(f"SMARTAccountFactory contract initialized at {self.factory_contract_address}.")

        self.relayer_contract_address = to_checksum_address(settings.SMART_RELAYER_ADDRESS)
        self.relayer_contract = self.w3.eth.contract(
            address=self.relayer_contract_address,
            abi=self.load_relayer_abi()
        )
        logger.info(f"SMARTRelayer contract initialized at {self.relayer_contract_address}.")

        self.lifecycle_contract_address = to_checksum_address(settings.SMART_LIFECYCLE_ADDRESS)
        self.lifecycle_contract = self.w3.eth.contract(
            address=self.lifecycle_contract_address,
            abi=self.load_lifecycle_abi()
        )
        logger.info(f"SMARTLifecycle contract initialized at {self.lifecycle_contract_address}.")

        self.lifecycle_relayer_contract_address = to_checksum_address(settings.SMART_LIFECYCLE_RELAYER_ADDRESS)
        self.lifecycle_relayer_contract = self.w3.eth.contract(
            address=self.lifecycle_relayer_contract_address,
            abi=self.load_lifecycle_relayer_abi()
        )
        logger.info(f"SMARTLifecycleRelayer contract initialized at {self.lifecycle_relayer_contract_address}.")

        try:
            private_key = settings.PRIVATE_KEY
            if private_key.startswith("0x"):
                private_key = private_key[2:]

            self.relayer_account = Account.from_key(private_key)
            logger.info(f"Relayer account loaded: {self.relayer_account.address}")
        except Exception as e:
            logger.error(f"Invalid private key provided: {str(e)}")
            raise ValueError("Invalid private key provided.")

        self.chain_id = int(settings.CHAIN_ID)
        self.max_gas_price = self.w3.to_wei(settings.MAX_GAS_PRICE, 'gwei')
        logger.info(f"SMARTChainManager initialized for contracts on chain ID {self.chain_id}.")

    def _extract_abi(self, data: dict | list) -> list:
        """Extract ABI from Hardhat artifact or return raw ABI if already a list."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and 'abi' in data:
            return data['abi']
        raise ValueError("Invalid ABI format: expected list or dict with 'abi' key")

    def load_factory_abi(self) -> list:
        """Load SMARTAccountFactory ABI"""
        abi_file_path = os.path.join(os.path.dirname(__file__), 'abis', 'SMARTAccountFactory.json')
        try:
            with open(abi_file_path, 'r') as file:
                data = json.load(file)
            abi = self._extract_abi(data)
            logger.info(f"SMARTAccountFactory ABI loaded from {abi_file_path}.")
            return abi
        except Exception as e:
            logger.error(f"Error loading SMARTAccountFactory ABI: {str(e)}")
            raise e

    def load_relayer_abi(self) -> list:
        """Load SMARTRelayer ABI for account operations"""
        abi_file_path = os.path.join(os.path.dirname(__file__), 'abis', 'SMARTRelayer.json')
        try:
            with open(abi_file_path, 'r') as file:
                data = json.load(file)
            abi = self._extract_abi(data)
            logger.info(f"SMARTRelayer ABI loaded from {abi_file_path}.")
            return abi
        except Exception as e:
            logger.error(f"Error loading SMARTRelayer ABI: {str(e)}")
            raise e

    def load_lifecycle_abi(self) -> list:
        """Load SMARTLifecycle ABI (ERC-721 + EIP-5192 Soulbound)"""
        abi_file_path = os.path.join(os.path.dirname(__file__), 'abis', 'SMARTLifecycle.json')
        try:
            with open(abi_file_path, 'r') as file:
                data = json.load(file)
            abi = self._extract_abi(data)
            logger.info(f"SMARTLifecycle ABI loaded from {abi_file_path}.")
            return abi
        except Exception as e:
            logger.error(f"Error loading SMARTLifecycle ABI: {str(e)}")
            raise e

    def load_lifecycle_relayer_abi(self) -> list:
        """Load SMARTLifecycleRelayer ABI for gasless model card operations"""
        abi_file_path = os.path.join(os.path.dirname(__file__), 'abis', 'SMARTLifecycleRelayer.json')
        try:
            with open(abi_file_path, 'r') as file:
                data = json.load(file)
            abi = self._extract_abi(data)
            logger.info(f"SMARTLifecycleRelayer ABI loaded from {abi_file_path}.")
            return abi
        except Exception as e:
            logger.error(f"Error loading SMARTLifecycleRelayer ABI: {str(e)}")
            raise e

    def is_valid_signature(self, signature: str) -> bool:
        """Validate the signature format (0x-prefixed 65-byte hex)."""
        if isinstance(signature, str) and signature.startswith("0x") and len(signature) == 132:
            return True
        return False

    async def is_registered_smart_account(self, smart_account_address: str) -> bool:
        """Return True if the SMARTAccount address has an owner on-chain."""
        try:
            if not is_address(smart_account_address):
                logger.error(f"Invalid Ethereum address provided: {smart_account_address}")
                raise HTTPException(status_code=400, detail="Invalid Ethereum address provided.")

            logger.debug(f"Checking if SMARTAccount '{smart_account_address}' is registered.")
            owner = await asyncio.to_thread(
                self.factory_contract.functions.ownerOfAccount(to_checksum_address(smart_account_address)).call
            )
            zero_address = "0x0000000000000000000000000000000000000000"
            is_registered = owner.lower() != zero_address.lower()
            logger.debug(f"SMARTAccount '{smart_account_address}' owner: {owner}, is_registered: {is_registered}")
            return is_registered
        except ContractLogicError as e:
            logger.error(f"ContractLogicError while checking registration: {str(e)}")
            raise HTTPException(status_code=400, detail=f"ContractLogicError: {str(e)}")
        except Exception as e:
            logger.error(f"Error checking registration on blockchain: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to check registration on blockchain.")

    async def check_if_registered(self, eoa_address: str) -> bool:
        """Return True if the EOA address has any SMARTAccounts registered."""
        try:
            if not is_address(eoa_address):
                logger.error(f"Invalid EOA address provided: {eoa_address}")
                raise HTTPException(status_code=400, detail="Invalid EOA address provided.")

            logger.debug(f"Checking if EOA '{eoa_address}' has SMARTAccounts.")
            accounts = await asyncio.to_thread(
                self.factory_contract.functions.getAccountsOfOwner(to_checksum_address(eoa_address)).call
            )
            is_registered = len(accounts) > 0
            logger.debug(f"EOA '{eoa_address}' has {len(accounts)} accounts. is_registered: {is_registered}")
            return is_registered
        except ContractLogicError as e:
            logger.error(f"ContractLogicError: {str(e)}")
            raise HTTPException(status_code=400, detail=f"ContractLogicError: {str(e)}")
        except Exception as e:
            logger.error(f"Error checking EOA registration: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to check EOA registration on blockchain.")

    async def verify_signature(self, registration_payload: dict, signature: str) -> bool:
        """Verify the EIP-712 signature of the registration payload."""
        try:
            logger.debug(f"Verifying signature for payload: {json.dumps(registration_payload, indent=2)}")

            if not self.is_valid_signature(signature):
                logger.error(f"Invalid signature format: {signature}")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid signature format. Ensure it is a 0x-prefixed hex string with 132 characters."
                )

            message_hash = eip712_encode_hash(registration_payload)
            logger.debug(f"Message hash for signature verification: {message_hash.hex()}")

            encoded_message = encode_defunct(hexstr=message_hash.hex())
            recovered_address = Account.recover_message(encoded_message, signature=HexBytes(signature))
            logger.debug(f"Recovered signer address: {recovered_address}")

            user = registration_payload['message']['eoa']
            user_address = to_checksum_address(user)
            logger.debug(f"User address from payload: {user_address}")

            if recovered_address.lower() != user_address.lower():
                logger.warning(f"Signature verification failed for user '{user_address}'.")
                raise HTTPException(status_code=400, detail="Invalid signature.")

            logger.info(f"Signature successfully verified for user '{user_address}'.")
            return True

        except HTTPException as he:
            raise he
        except Exception as e:
            logger.exception(f"Error verifying signature: {str(e)}")
            return False

    async def create_account_with_username_gasless(self, eoa_address: str, username: str) -> Dict[str, str]:
        """Create AIDeveloper and Reader SMARTAccounts, gas paid by the relayer."""
        try:
            logger.debug(f"Creating SMARTAccounts for EOA '{eoa_address}' with username '{username}'.")

            if not is_address(eoa_address):
                logger.error(f"Invalid EOA address provided: {eoa_address}")
                raise HTTPException(status_code=400, detail="Invalid EOA address provided.")

            eoa_address = to_checksum_address(eoa_address)

            if not username or not isinstance(username, str):
                logger.error("Username cannot be empty and must be a string.")
                raise HTTPException(status_code=400, detail="Username cannot be empty and must be a string.")

            accounts = {}

            logger.debug(f"Creating AIDeveloper SMARTAccount for '{username}'")
            txn = self.factory_contract.functions.createAccount(
                eoa_address,
                username,
                1
            ).build_transaction({
                'from': self.relayer_account.address,
                'nonce': await self.get_nonce(self.relayer_account.address),
                'gasPrice': min(self.w3.eth.gas_price, self.max_gas_price),
                'chainId': self.chain_id
            })

            gas_estimate = await asyncio.to_thread(self.w3.eth.estimate_gas, txn)
            txn['gas'] = gas_estimate
            logger.debug(f"Estimated gas for AIDeveloper account: {gas_estimate}")

            signed_txn = self.w3.eth.account.sign_transaction(txn, private_key=self.relayer_account.key)
            txn_hash = await asyncio.to_thread(self.w3.eth.send_raw_transaction, signed_txn.rawTransaction)
            logger.info(f"AIDeveloper account creation transaction sent: {txn_hash.hex()}")

            txn_receipt = await asyncio.to_thread(self.w3.eth.wait_for_transaction_receipt, txn_hash, timeout=120)
            logger.info(f"AIDeveloper SMARTAccount created. Receipt: {txn_receipt.transactionHash.hex()}")

            ai_developer_account = await asyncio.to_thread(
                self.factory_contract.functions.accountOfUsername(username, 1).call
            )
            logger.info(f"AIDeveloper SMARTAccount address: {ai_developer_account}")
            accounts["AIDeveloper"] = ai_developer_account

            logger.debug(f"Creating Reader SMARTAccount for '{username}'")
            nonce = await self.get_nonce(self.relayer_account.address)
            txn = self.factory_contract.functions.createAccount(
                eoa_address,
                username,
                0
            ).build_transaction({
                'from': self.relayer_account.address,
                'nonce': nonce,
                'gasPrice': min(self.w3.eth.gas_price, self.max_gas_price),
                'chainId': self.chain_id
            })

            gas_estimate = await asyncio.to_thread(self.w3.eth.estimate_gas, txn)
            txn['gas'] = gas_estimate
            logger.debug(f"Estimated gas for Reader account: {gas_estimate}")

            signed_txn = self.w3.eth.account.sign_transaction(txn, private_key=self.relayer_account.key)
            txn_hash = await asyncio.to_thread(self.w3.eth.send_raw_transaction, signed_txn.rawTransaction)
            logger.info(f"Reader account creation transaction sent: {txn_hash.hex()}")

            txn_receipt = await asyncio.to_thread(self.w3.eth.wait_for_transaction_receipt, txn_hash, timeout=120)
            logger.info(f"Reader SMARTAccount created. Receipt: {txn_receipt.transactionHash.hex()}")

            reader_account = await asyncio.to_thread(
                self.factory_contract.functions.accountOfUsername(username, 0).call
            )
            logger.info(f"Reader SMARTAccount address: {reader_account}")
            accounts["Reader"] = reader_account

            return accounts

        except ContractLogicError as e:
            logger.error(f"ContractLogicError during account creation: {str(e)}")
            raise HTTPException(status_code=400, detail=f"ContractLogicError: {str(e)}")
        except HTTPException as he:
            raise he
        except Exception as e:
            logger.exception(f"Error during account creation on blockchain: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create account on the blockchain.")

    async def create_single_account_gasless(self, eoa_address: str, username: str, role: int) -> str:
        """Create a single SMARTAccount with role (0=Reader,1=AIDeveloper,2=Reviewer,3=Publisher,4=Admin)."""
        try:
            logger.debug(f"Creating single SMARTAccount for EOA '{eoa_address}' with username '{username}' and role {role}.")

            if not is_address(eoa_address):
                logger.error(f"Invalid EOA address provided: {eoa_address}")
                raise HTTPException(status_code=400, detail="Invalid EOA address provided.")

            eoa_address = to_checksum_address(eoa_address)

            role_names = {0: "Reader", 1: "AIDeveloper", 2: "Reviewer", 3: "Publisher", 4: "Admin"}
            role_name = role_names.get(role, f"Role{role}")

            logger.debug(f"Creating {role_name} SMARTAccount for '{username}'")
            txn = self.factory_contract.functions.createAccount(
                eoa_address,
                username,
                role
            ).build_transaction({
                'from': self.relayer_account.address,
                'nonce': await self.get_nonce(self.relayer_account.address),
                'gasPrice': min(self.w3.eth.gas_price, self.max_gas_price),
                'chainId': self.chain_id
            })

            gas_estimate = await asyncio.to_thread(self.w3.eth.estimate_gas, txn)
            txn['gas'] = gas_estimate

            signed_txn = self.w3.eth.account.sign_transaction(txn, private_key=self.relayer_account.key)
            txn_hash = await asyncio.to_thread(self.w3.eth.send_raw_transaction, signed_txn.rawTransaction)
            logger.info(f"{role_name} SMARTAccount creation transaction sent: {txn_hash.hex()}")

            txn_receipt = await asyncio.to_thread(self.w3.eth.wait_for_transaction_receipt, txn_hash, timeout=120)
            logger.info(f"{role_name} SMARTAccount created. Receipt: {txn_receipt.transactionHash.hex()}")

            account_address = await asyncio.to_thread(
                self.factory_contract.functions.accountOfUsername(username, role).call
            )
            logger.info(f"{role_name} SMARTAccount address: {account_address}")

            return account_address

        except ContractLogicError as e:
            logger.error(f"ContractLogicError during single account creation: {str(e)}")
            raise HTTPException(status_code=400, detail=f"ContractLogicError: {str(e)}")
        except HTTPException as he:
            raise he
        except Exception as e:
            logger.exception(f"Error during single account creation: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create account on the blockchain.")

    async def create_model_card_gasless(self, smart_account: str, token_id: int, data: str, name: str) -> Dict:
        """Create a new model card (soulbound token) on-chain via SMARTLifecycleRelayer."""
        try:
            logger.debug(f"Creating model card with token ID '{token_id}' by SMARTAccount '{smart_account}'.")

            if not Web3.is_address(smart_account):
                logger.error(f"Invalid SMARTAccount address provided: {smart_account}")
                raise HTTPException(status_code=400, detail="Invalid SMARTAccount address provided.")

            smart_account = Web3.to_checksum_address(smart_account)

            if not isinstance(token_id, int):
                try:
                    token_id = int(token_id)
                except ValueError:
                    logger.error(f"token_id must be an integer")
                    raise HTTPException(status_code=400, detail="token_id must be an integer.")

            try:
                data_bytes = bytes(data, 'utf-8')
            except Exception as e:
                logger.error(f"Failed to convert data to bytes: {str(e)}")
                raise HTTPException(status_code=400, detail="Invalid data format.")

            txn = self.lifecycle_relayer_contract.functions.relayGaslessCreateModelCard(
                smart_account,
                token_id,
                data_bytes,
                name
            ).build_transaction({
                'from': self.relayer_account.address,
                'nonce': await self.get_nonce(self.relayer_account.address),
                'gasPrice': min(self.w3.eth.gas_price, self.max_gas_price),
                'chainId': self.chain_id
            })

            gas_estimate = await asyncio.to_thread(self.w3.eth.estimate_gas, txn)
            txn['gas'] = gas_estimate

            signed_txn = self.w3.eth.account.sign_transaction(txn, private_key=self.relayer_account.key)
            txn_hash = await asyncio.to_thread(self.w3.eth.send_raw_transaction, signed_txn.rawTransaction)
            logger.info(f"Model card creation transaction sent with hash: {txn_hash.hex()}")

            txn_receipt = await asyncio.to_thread(self.w3.eth.wait_for_transaction_receipt, txn_hash, timeout=120)
            logger.info(f"Transaction receipt received: {txn_receipt.transactionHash.hex()}")

            try:
                events = self.lifecycle_relayer_contract.events.UserOperationRelayed().process_receipt(txn_receipt)
            except Exception as e:
                logger.error(f"Failed to parse events: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to parse transaction events.")

            if not events:
                logger.error("ModelCardCreated event not found in transaction logs.")
                raise HTTPException(status_code=500, detail="Failed to confirm model card creation.")

            logger.info(f"Model card created successfully with token ID '{token_id}'.")
            return {"success": True, "token_id": token_id}

        except ContractLogicError as e:
            logger.error(f"ContractLogicError during model card creation: {str(e)}")
            return {"success": False, "error": f"ContractLogicError: {str(e)}"}
        except HTTPException as e:
            raise e
        except MismatchedABI as e:
            logger.exception(f"MismatchedABI: {str(e)}")
            raise HTTPException(status_code=500, detail="ABI mismatch when interacting with the smart contract.")
        except Exception as e:
            logger.exception(f"Error during model card creation: {str(e)}")
            return {"success": False, "error": "Failed to create model card on blockchain."}

    async def create_model_card_version_gasless(self, smart_account: str, base_token_id: int, version_token_id: int, data: str, name: str) -> Dict:
        """Create a new version of an existing model card on-chain."""
        try:
            logger.debug(f"Creating versioned model card with token ID '{version_token_id}' based on '{base_token_id}'.")

            if not is_address(smart_account):
                logger.error(f"Invalid SMARTAccount address: {smart_account}")
                raise HTTPException(status_code=400, detail="Invalid SMARTAccount address provided.")

            smart_account = to_checksum_address(smart_account)

            txn = self.lifecycle_relayer_contract.functions.createModelCardVersion(
                base_token_id,
                version_token_id,
                data,
                name
            ).build_transaction({
                'from': smart_account,
                'nonce': await self.get_nonce(smart_account),
                'gasPrice': min(self.w3.eth.gas_price, self.max_gas_price),
                'chainId': self.chain_id
            })

            gas_estimate = await asyncio.to_thread(self.w3.eth.estimate_gas, txn)
            txn['gas'] = gas_estimate

            signed_txn = self.w3.eth.account.sign_transaction(txn, private_key=self.relayer_account.key)
            txn_hash = await asyncio.to_thread(self.w3.eth.send_raw_transaction, signed_txn.rawTransaction)
            logger.info(f"Model card version creation transaction sent: {txn_hash.hex()}")

            txn_receipt = await asyncio.to_thread(self.w3.eth.wait_for_transaction_receipt, txn_hash, timeout=120)
            logger.info(f"Transaction receipt: {txn_receipt.transactionHash.hex()}")

            events = self.lifecycle_relayer_contract.events.ModelCardVersionCreated().process_receipt(txn_receipt)

            if not events:
                logger.error("ModelCardVersionCreated event not found.")
                raise HTTPException(status_code=500, detail="Failed to confirm model card version creation.")

            logger.info(f"Model card version created with token ID '{version_token_id}'.")
            return {"success": True, "token_id": version_token_id}

        except ContractLogicError as e:
            logger.error(f"ContractLogicError: {str(e)}")
            return {"success": False, "error": f"ContractLogicError: {str(e)}"}
        except Exception as e:
            logger.exception(f"Error during model card version creation: {str(e)}")
            return {"success": False, "error": "Failed to create model card version on blockchain."}

    async def get_model_by_token_id(self, token_id: int) -> Optional[Dict]:
        """Retrieve model card details by token ID."""
        try:
            logger.debug(f"Retrieving model card details for token ID '{token_id}'.")

            model_details = await asyncio.to_thread(
                self.lifecycle_contract.functions.getTokenName(token_id).call
            )

            model_data = {
                "id": model_details[0],
                "name": model_details[1],
                "data": model_details[2],
                "owner": model_details[3]
            }

            logger.info(f"Model card retrieved for token ID '{token_id}'.")
            return model_data

        except ContractLogicError as e:
            logger.error(f"ContractLogicError: {str(e)}")
            raise HTTPException(status_code=400, detail=f"ContractLogicError: {str(e)}")
        except Exception as e:
            logger.exception(f"Error retrieving model card: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to retrieve model card from blockchain.")

    async def get_nonce(self, address: str) -> int:
        """Return the pending nonce for the given address."""
        try:
            nonce = await asyncio.to_thread(self.w3.eth.get_transaction_count, address, "pending")
            logger.debug(f"Retrieved nonce for address '{address}' (pending): {nonce}")
            return nonce
        except Exception as e:
            logger.exception(f"Error retrieving nonce: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to retrieve nonce.")


smart_chain_manager = SMARTChainManager()

async def is_registered_smart_account(smart_account_address: str) -> bool:
    return await smart_chain_manager.is_registered_smart_account(smart_account_address)

async def verify_signature(registration_payload: dict, signature: str) -> bool:
    return await smart_chain_manager.verify_signature(registration_payload, signature)

async def create_account_with_username_gasless(eoa_address: str, username: str) -> Dict[str, str]:
    return await smart_chain_manager.create_account_with_username_gasless(eoa_address, username)

async def check_if_registered(eoa_address: str) -> bool:
    return await smart_chain_manager.check_if_registered(eoa_address)

async def create_model_card_gasless(smart_account: str, token_id: int, data: str, name: str) -> Dict:
    return await smart_chain_manager.create_model_card_gasless(smart_account, token_id, data, name)

async def create_model_card_version_gasless(smart_account: str, base_token_id: int, version_token_id: int, data: str, name: str) -> Dict:
    return await smart_chain_manager.create_model_card_version_gasless(smart_account, base_token_id, version_token_id, data, name)

async def get_model_by_token_id(token_id: int) -> Optional[Dict]:
    return await smart_chain_manager.get_model_by_token_id(token_id)

async def create_single_account_gasless(eoa_address: str, username: str, role: int) -> str:
    return await smart_chain_manager.create_single_account_gasless(eoa_address, username, role)

is_registered_clone = is_registered_smart_account
lucechain_manager = smart_chain_manager
