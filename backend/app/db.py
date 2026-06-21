
import os
import logging
from neo4j import AsyncGraphDatabase, exceptions
from neo4j.exceptions import Neo4jError
from typing import Dict, Any, Optional, List
from fastapi import HTTPException
from contextlib import asynccontextmanager
import json
import secrets
import time


logger = logging.getLogger("db")
logger.setLevel(logging.INFO)  
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)


RELAX_SCHEMA = os.getenv("LUCE_RELAX_MODEL_CARD_SCHEMA", "false").lower() in {"1", "true", "yes"}

def _alias_and_stub_model_data(model_data: Dict[str, Any], *, relaxed: bool) -> Dict[str, Any]:
    """Normalize aliases and stub missing sections (if relaxed) without mutating the original."""
    md = dict(model_data or {})

    if "model_detail" not in md and "model_details" in md:
        md["model_detail"] = md.get("model_details") or {}

    if relaxed:
        md.setdefault("model_detail", {
            "model_id": None,
            "summary": None,
            "motivation": None,
            "tasks": None,
            "use_cases": None,
            "benefits": None
        })
        md.setdefault("quantitative_analysis", {
            "accuracy": None,
            "precision": None
        })
        md.setdefault("qualitative_analysis", {
            "strengths": [],
            "weaknesses": []
        })

    return md



class Neo4jConnection:
    def __init__(self, uri: str, user: Optional[str] = None, password: Optional[str] = None):
        """Initialize the Neo4j connection with optional authentication."""
        try:
            if user and password:
                self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
                logger.info(f"Connected to Neo4j at {uri} as user '{user}'.")
            else:
                self._driver = AsyncGraphDatabase.driver(uri)
                logger.info(f"Connected to Neo4j at {uri} without authentication.")
        except Exception as e:
            logger.exception(f"Failed to create Neo4j driver: {str(e)}")
            raise e

    async def close(self):
        """Close the Neo4j driver connection."""
        try:
            await self._driver.close()
            logger.info("Neo4j connection closed.")
        except Exception as e:
            logger.exception(f"Error closing Neo4j connection: {str(e)}")
            raise e

    @asynccontextmanager
    async def transaction(self):
        """Transactional context for executing Neo4j operations atomically."""
        async with self._driver.session() as session:
            tx = await session.begin_transaction()
            try:
                yield tx
                await tx.commit()
            except Exception as e:
                await tx.rollback()
                logger.exception(f"Transaction failed and rolled back: {str(e)}")
                raise e

    async def query(self, query: str, parameters: Optional[dict] = None) -> List[Dict]:
        """Execute a read query and return the records."""
        async with self._driver.session() as session:
            try:
                logger.debug(f"Executing query: {query} with parameters: {parameters}")
                result = await session.run(query, parameters)
                records = [record.data() async for record in result]
                logger.debug(f"Query returned {len(records)} records.")
                return records
            except exceptions.Neo4jError as e:
                logger.error(f"Neo4jError executing query: {str(e)}")
                raise e
            except Exception as e:
                logger.exception(f"Unexpected error executing query: {str(e)}")
                raise e

    async def execute(self, query: str, parameters: Optional[dict] = None, tx: Optional[Any] = None):
        """Execute a write query, optionally within a transaction."""
        try:
            if tx:
                logger.debug(f"Executing write query within transaction: {query} with parameters: {parameters}")
                await tx.run(query, parameters)
            else:
                async with self._driver.session() as session:
                    logger.debug(f"Executing write query: {query} with parameters: {parameters}")
                    await session.execute_write(lambda tx_inner: tx_inner.run(query, parameters))
            logger.debug("Write query executed successfully.")
        except exceptions.Neo4jError as e:
            logger.error(f"Neo4jError executing write query: {str(e)}")
            raise e
        except Exception as e:
            logger.exception(f"Unexpected error executing write query: {str(e)}")
            raise e

    async def initialize_schema(self):
        """Create the schema constraints and indexes; run once at setup."""
        try:
            logger.info("Initializing Neo4j schema...")
            await self.execute("""
                CREATE CONSTRAINT IF NOT EXISTS 
                FOR (u:User) 
                REQUIRE u.uuid IS UNIQUE
            """)
            logger.info("Uniqueness constraint on 'User.uuid' ensured.")

            await self.execute("""
                CREATE CONSTRAINT IF NOT EXISTS 
                FOR (u:User) 
                REQUIRE u.eoa_address IS UNIQUE
            """)
            logger.info("Uniqueness constraint on 'User.eoa_address' ensured.")

            await self.execute("""
                CREATE CONSTRAINT IF NOT EXISTS 
                FOR (c:CustomAccount) 
                REQUIRE c.address IS UNIQUE
            """)
            logger.info("Uniqueness constraint on 'CustomAccount.address' ensured.")

            await self.execute("""
                CREATE CONSTRAINT IF NOT EXISTS 
                FOR (r:Role) 
                REQUIRE r.name IS UNIQUE
            """)
            logger.info("Uniqueness constraint on 'Role.name' ensured.")

            await self.execute("""
                CREATE INDEX IF NOT EXISTS
                FOR (m:ModelCard)
                ON (m.token_id)
            """)
            logger.info("Index on 'ModelCard.token_id' ensured.")

            await self.execute("""
                CREATE INDEX IF NOT EXISTS
                FOR (m:ModelCard)
                ON (m.developer_organization, m.model_name)
            """)
            logger.info("Composite index on 'ModelCard.(developer_organization, model_name)' ensured.")

            await self.execute("""
                CREATE INDEX IF NOT EXISTS
                FOR (m:ModelCard)
                ON (m.model_name)
            """)
            logger.info("Index on 'ModelCard.model_name' ensured.")

            await self.execute("""
                CREATE INDEX IF NOT EXISTS 
                FOR (md:ModelDetail) 
                ON (md.model_id)
            """)
            logger.info("Index on 'ModelDetail.model_id' ensured.")

            await self.execute("""
                CREATE INDEX IF NOT EXISTS 
                FOR (qa:QuantitativeAnalysis) 
                ON (qa.token_id)
            """)
            logger.info("Index on 'QuantitativeAnalysis.token_id' ensured.")

            await self.execute("""
                CREATE INDEX IF NOT EXISTS 
                FOR (qla:QualitativeAnalysis) 
                ON (qla.token_id)
            """)
            logger.info("Index on 'QualitativeAnalysis.token_id' ensured.")

            default_roles = ['Reader', 'AIDeveloper', 'Reviewer', 'Publisher', 'Admin', 'User']
            for role in default_roles:
                await self.create_role(role)

            logger.info("Neo4j schema initialization completed.")
        except Exception as e:
            logger.exception(f"Error initializing Neo4j schema: {str(e)}")
            raise e

    async def create_user(
        self,
        uuid: str,
        eoa_address: str,
        otp: str,
        otp_expires_at: float,
        private_key: str,
        signature: str,
        signature_verified: bool,
        status: str = "registration_in_progress",
        tx: Optional[Any] = None,
        luceid: str = None,
        smart_id: str = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
    ):
        """Create or update a User node in Neo4j."""
        identifier = smart_id or luceid
        if not identifier:
            raise ValueError("Either smart_id or luceid must be provided")

        query = """
        MERGE (u:User {uuid: $uuid})
        SET u.eoa_address = $eoa_address,
            u.smart_id = $smart_id,
            u.luceid = $smart_id,
            u.otp = $otp,
            u.otp_expires_at = $otp_expires_at,
            u.verified = false,
            u.private_key = $private_key,
            u.signature = $signature,
            u.signature_verified = $signature_verified,
            u.status = $status,
            u.username = coalesce($username, u.username),
            u.email = coalesce($email, u.email),
            u.created_at = coalesce(u.created_at, timestamp())
        """
        parameters = {
            "uuid": uuid,
            "eoa_address": eoa_address,
            "smart_id": identifier,
            "otp": otp,
            "otp_expires_at": otp_expires_at,
            "private_key": private_key,
            "signature": signature,
            "signature_verified": signature_verified,
            "status": status,
            "username": username,
            "email": email,
        }
        try:
            if tx:
                logger.debug(f"Creating or updating User node for UUID '{uuid}' within transaction.")
                await tx.run(query, parameters)
            else:
                logger.debug(f"Creating or updating User node for UUID '{uuid}'.")
                await self.execute(query, parameters)
            logger.info(f"User '{uuid}' created or updated successfully in Neo4j.")
        except Exception as e:
            logger.exception(f"Error creating/updating User '{uuid}': {str(e)}")
            raise e

    async def get_user_by_uuid(self, uuid: str, tx: Optional[Any] = None) -> Optional[Dict]:
        """Retrieve a User node by UUID, or None."""
        query = """
        MATCH (u:User {uuid: $uuid})
        RETURN u.eoa_address AS eoa_address,
               u.verified AS verified,
               u.signature AS signature,
               coalesce(u.smart_id, u.luceid) AS smart_id,
               u.luceid AS luceid,
               u.status AS status,
               u.username AS username,
               u.email AS email,
               u.created_at AS created_at,
               u.role AS role
        """
        parameters = {"uuid": uuid}
        try:
            if tx:
                logger.debug(f"Retrieving User node for UUID '{uuid}' within transaction.")
                result = await tx.run(query, parameters)
                records = [record.data() async for record in result]
            else:
                logger.debug(f"Retrieving User node for UUID '{uuid}'.")
                records = await self.query(query, parameters)
            
            if records:
                user_data = records[0]
                logger.debug(f"Retrieved User for UUID '{uuid}': {user_data}")
                return user_data
            else:
                logger.debug(f"No User found for UUID '{uuid}'.")
                return None
        except Exception as e:
            logger.exception(f"Error retrieving User '{uuid}': {str(e)}")
            raise e

    async def update_user_profile(
        self,
        uuid: str,
        username: Optional[str] = None,
        email: Optional[str] = None,
        tx: Optional[Any] = None,
    ) -> bool:
        """Update profile fields (username, email) on a User node; returns True if it exists."""
        query = """
        MATCH (u:User {uuid: $uuid})
        SET u.username = coalesce($username, u.username),
            u.email = coalesce($email, u.email),
            u.created_at = coalesce(u.created_at, timestamp())
        RETURN u.uuid AS uuid
        """
        parameters = {"uuid": uuid, "username": username, "email": email}
        try:
            if tx:
                result = await tx.run(query, parameters)
                records = [r.data() async for r in result]
            else:
                records = await self.query(query, parameters)
            return bool(records)
        except Exception as e:
            logger.exception(f"Error updating profile for User '{uuid}': {str(e)}")
            raise e

    async def update_otp(self, uuid: str, otp: str, otp_expires_at: float, tx: Optional[Any] = None):
        """Update the OTP and its expiration for a user."""
        query = """
        MATCH (u:User {uuid: $uuid})
        SET u.otp = $otp,
            u.otp_expires_at = $otp_expires_at,
            u.signature_verified = false
        """
        parameters = {
            "uuid": uuid,
            "otp": otp,
            "otp_expires_at": otp_expires_at
        }
        try:
            if tx:
                logger.debug(f"Updating OTP for User '{uuid}' within transaction.")
                await tx.run(query, parameters)
            else:
                logger.debug(f"Updating OTP for User '{uuid}'.")
                await self.execute(query, parameters)
            logger.info(f"OTP for User '{uuid}' updated successfully.")
        except Exception as e:
            logger.exception(f"Error updating OTP for User '{uuid}': {str(e)}")
            raise e

    async def update_signature(self, uuid: str, signature: str, signature_verified: bool, tx: Optional[Any] = None):
        """Update the signature and its verification status for a user."""
        query = """
        MATCH (u:User {uuid: $uuid})
        SET u.signature = $signature,
            u.signature_verified = $signature_verified
        """
        parameters = {
            "uuid": uuid,
            "signature": signature,
            "signature_verified": signature_verified
        }
        try:
            if tx:
                logger.debug(f"Updating signature for User '{uuid}' within transaction.")
                await tx.run(query, parameters)
            else:
                logger.debug(f"Updating signature for User '{uuid}'.")
                await self.execute(query, parameters)
            logger.info(f"Signature for User '{uuid}' updated successfully.")
        except Exception as e:
            logger.exception(f"Error updating signature for User '{uuid}': {str(e)}")
            raise e

    async def verify_otp(self, uuid: str, otp: str) -> bool:
        """Return True if the OTP is valid and not expired for the given UUID."""
        query = """
        MATCH (u:User {uuid: $uuid})
        RETURN u.otp AS otp, u.otp_expires_at AS otp_expires_at
        """
        parameters = {"uuid": uuid}
        try:
            logger.debug(f"Retrieving OTP for UUID '{uuid}'.")
            result = await self.query(query, parameters)
            if not result:
                logger.warning(f"No user found with UUID '{uuid}'.")
                return False

            stored_otp = result[0].get("otp")
            otp_expires_at = result[0].get("otp_expires_at")

            if stored_otp != otp:
                logger.warning(f"Provided OTP '{otp}' does not match stored OTP for UUID '{uuid}'.")
                return False

            current_time = time.time()
            if current_time > otp_expires_at:
                logger.warning(f"OTP for UUID '{uuid}' has expired.")
                return False

            await self.invalidate_otp(uuid)
            logger.info(f"OTP for UUID '{uuid}' verified successfully.")

            await self.set_verified(uuid, True)
            logger.info(f"User '{uuid}' marked as verified.")

            return True

        except Exception as e:
            logger.exception(f"Error verifying OTP for UUID '{uuid}': {str(e)}")
            return False

    async def invalidate_otp(self, uuid: str, tx: Optional[Any] = None):
        """Invalidate the OTP for the given UUID to prevent reuse."""
        query = """
        MATCH (u:User {uuid: $uuid})
        SET u.otp = NULL, u.otp_expires_at = NULL
        """
        parameters = {"uuid": uuid}
        try:
            if tx:
                logger.debug(f"Invalidating OTP for UUID '{uuid}' within transaction.")
                await tx.run(query, parameters)
            else:
                logger.debug(f"Invalidating OTP for UUID '{uuid}'.")
                await self.execute(query, parameters)
            logger.info(f"OTP for UUID '{uuid}' invalidated.")
        except Exception as e:
            logger.exception(f"Error invalidating OTP for User '{uuid}': {str(e)}")
            raise e

    async def set_verified(self, uuid: str, status: bool, tx: Optional[Any] = None):
        """Set the verified status for a user."""
        query = """
        MATCH (u:User {uuid: $uuid})
        SET u.verified = $status
        """
        parameters = {
            "uuid": uuid,
            "status": status
        }
        try:
            if tx:
                logger.debug(f"Setting verified='{status}' for User '{uuid}' within transaction.")
                await tx.run(query, parameters)
            else:
                logger.debug(f"Setting verified='{status}' for User '{uuid}'.")
                await self.execute(query, parameters)
            logger.info(f"Verified status set to '{status}' for User '{uuid}'.")
        except Exception as e:
            logger.exception(f"Error setting verified status for User '{uuid}': {str(e)}")
            raise e

    async def reset_verified_flag(self, uuid: str, tx: Optional[Any] = None):
        """Reset the verified flag to false for a user."""
        query = """
        MATCH (u:User {uuid: $uuid})
        SET u.verified = false
        """
        parameters = {"uuid": uuid}
        try:
            if tx:
                logger.debug(f"Resetting verified flag for UUID '{uuid}' within transaction.")
                await tx.run(query, parameters)
            else:
                logger.debug(f"Resetting verified flag for UUID '{uuid}'.")
                await self.execute(query, parameters)
            logger.info(f"Verified flag reset to 'false' for UUID '{uuid}'.")
        except Exception as e:
            logger.exception(f"Error resetting verified flag for UUID '{uuid}': {str(e)}")
            raise e

    async def delete_user_if_registration_failed(self, uuid: str, tx: Optional[Any] = None):
        """Delete a user node if its registration failed."""
        query = """
        MATCH (u:User {uuid: $uuid})
        WHERE u.status = 'registration_failed'
        DETACH DELETE u
        """
        parameters = {"uuid": uuid}
        try:
            if tx:
                logger.debug(f"Deleting User '{uuid}' within transaction due to failed registration.")
                await tx.run(query, parameters)
            else:
                logger.debug(f"Deleting User '{uuid}' due to failed registration.")
                await self.execute(query, parameters)
            logger.info(f"User '{uuid}' deleted from Neo4j due to failed registration.")
        except Exception as e:
            logger.exception(f"Error deleting User '{uuid}': {str(e)}")
            raise e     

    async def update_user_status(self, uuid: str, status: str, tx: Optional[Any] = None):
        """Update the status of a user."""
        query = """
        MATCH (u:User {uuid: $uuid})
        SET u.status = $status
        """
        parameters = {
            "uuid": uuid,
            "status": status
        }
        try:
            if tx:
                logger.debug(f"Updating status to '{status}' for User '{uuid}' within transaction.")
                await tx.run(query, parameters)
            else:
                logger.debug(f"Updating status to '{status}' for User '{uuid}'.")
                await self.execute(query, parameters)
            logger.info(f"Status updated to '{status}' for User '{uuid}'.")
        except Exception as e:
            logger.exception(f"Error updating status for User '{uuid}': {str(e)}")
            raise e

    async def set_signature_verified(self, uuid: str, status: bool, tx: Optional[Any] = None):
        """Set the signature verification status for a user."""
        query = """
        MATCH (u:User {uuid: $uuid})
        SET u.signature_verified = $status
        """
        parameters = {
            "uuid": uuid,
            "status": status
        }
        try:
            if tx:
                logger.debug(f"Setting signature_verified='{status}' for User '{uuid}' within transaction.")
                await tx.run(query, parameters)
            else:
                logger.debug(f"Setting signature_verified='{status}' for User '{uuid}'.")
                await self.execute(query, parameters)
            logger.info(f"Signature verification status set to '{status}' for User '{uuid}'.")
        except Exception as e:
            logger.exception(f"Error setting signature_verified for User '{uuid}': {str(e)}")
            raise e

    async def get_custom_account(self, uuid: str) -> Optional[str]:
        """Retrieve the custom account address for a user, or None."""
        query = """
        MATCH (u:User {uuid: $uuid})-[:HAS_CUSTOM_ACCOUNT]->(c:CustomAccount)
        RETURN c.address AS address
        """
        parameters = {"uuid": uuid}
        try:
            logger.debug(f"Retrieving custom account for User '{uuid}'.")
            result = await self.query(query, parameters)
            if result:
                custom_account_address = result[0].get("address")
                logger.debug(f"Custom account for User '{uuid}': {custom_account_address}")
                return custom_account_address
            else:
                logger.debug(f"No custom account found for User '{uuid}'.")
                return None
        except Exception as e:
            logger.exception(f"Error retrieving custom account for User '{uuid}': {str(e)}")
            raise e

    async def store_custom_account(self, uuid: str, address: str, role: str, tx: Optional[Any] = None):
        """Store a custom account address and its role for a user. Legacy; prefer store_smart_account."""
        query = """
        MATCH (u:User {uuid: $uuid})
        MERGE (c:CustomAccount:SMARTAccount {address: $address})
        MERGE (r:Role {name: $role})
        MERGE (u)-[:HAS_CUSTOM_ACCOUNT]->(c)
        MERGE (u)-[:HAS_SMART_ACCOUNT]->(c)
        MERGE (c)-[:HAS_ROLE]->(r)
        """
        parameters = {
            "uuid": uuid,
            "address": address,
            "role": role
        }
        try:
            if tx:
                logger.debug(f"Storing account '{address}' with role '{role}' for User '{uuid}' within transaction.")
                await tx.run(query, parameters)
            else:
                logger.debug(f"Storing account '{address}' with role '{role}' for User '{uuid}'.")
                await self.execute(query, parameters)
            logger.info(f"Account '{address}' with role '{role}' stored for User '{uuid}'.")
        except Exception as e:
            logger.exception(f"Error storing account '{address}' for User '{uuid}': {str(e)}")
            raise e

    async def store_smart_account(self, uuid: str, address: str, role: str, tx: Optional[Any] = None):
        """Store a SMARTAccount address and its role for a user."""
        return await self.store_custom_account(uuid, address, role, tx)

    async def get_private_key(self, uuid: str, tx: Optional[Any] = None) -> Optional[str]:
        """Retrieve the private key for a user, or None."""
        query = """
        MATCH (u:User {uuid: $uuid})
        RETURN u.private_key AS private_key
        """
        parameters = {"uuid": uuid}
        try:
            if tx:
                logger.debug(f"Retrieving private key for User '{uuid}' within transaction.")
                result = await tx.run(query, parameters)
                records = [record.data() async for record in result]
            else:
                logger.debug(f"Retrieving private key for User '{uuid}'.")
                records = await self.query(query, parameters)

            if records:
                private_key = records[0].get("private_key")
                logger.debug(f"Private key retrieved for User '{uuid}'.")
                return private_key
            else:
                logger.debug(f"No private key found for User '{uuid}'.")
                return None
        except Exception as e:
            logger.exception(f"Error retrieving private key for User '{uuid}': {str(e)}")
            raise e

    async def get_private_key_by_address(self, address: str, tx: Optional[Any] = None) -> Optional[str]:
        """Retrieve the private key for a user by EOA or custom account address, or None."""
        query = """
        MATCH (u:User)
        WHERE u.eoa_address = $address OR u.eoa_address = toLower($address)
        RETURN u.private_key AS private_key
        UNION
        MATCH (u:User)-[:HAS_CUSTOM_ACCOUNT]->(ca:CustomAccount)
        WHERE ca.address = $address OR ca.address = toLower($address)
        RETURN u.private_key AS private_key
        """
        parameters = {"address": address}
        try:
            if tx:
                logger.debug(f"Retrieving private key by address '{address}' within transaction.")
                result = await tx.run(query, parameters)
                records = [record.data() async for record in result]
            else:
                logger.debug(f"Retrieving private key by address '{address}'.")
                records = await self.query(query, parameters)

            if records:
                private_key = records[0].get("private_key")
                logger.debug(f"Private key found for address '{address}'")
                return private_key
            else:
                logger.debug(f"No private key found for address '{address}'.")
                return None
        except Exception as e:
            logger.exception(f"Error retrieving private key by address '{address}': {str(e)}")
            raise e

    async def create_role(self, role_name: str, tx: Optional[Any] = None):
        """Create a Role node if it doesn't exist."""
        query = """
        MERGE (r:Role {name: $role_name})
        """
        parameters = {"role_name": role_name}
        try:
            if tx:
                logger.debug(f"Creating or ensuring existence of Role '{role_name}' within transaction.")
                await tx.run(query, parameters)
            else:
                logger.debug(f"Creating or ensuring existence of Role '{role_name}'.")
                await self.execute(query, parameters)
            logger.info(f"Role '{role_name}' ensured in Neo4j.")
        except Exception as e:
            logger.exception(f"Error creating Role '{role_name}': {str(e)}")
            raise e

    async def get_user_roles(self, uuid: str, tx: Optional[Any] = None) -> List[str]:
        """Retrieve the roles across all CustomAccounts of a user."""
        query = """
        MATCH (u:User {uuid: $uuid})-[:HAS_CUSTOM_ACCOUNT]->(:CustomAccount)-[:HAS_ROLE]->(r:Role)
        RETURN DISTINCT r.name AS role
        """
        parameters = {"uuid": uuid}
        try:
            if tx:
                logger.debug(f"Retrieving roles for User '{uuid}' via CustomAccounts within transaction.")
                result = await tx.run(query, parameters)
                records = [record.data() async for record in result]
            else:
                logger.debug(f"Retrieving roles for User '{uuid}' via CustomAccounts.")
                records = await self.query(query, parameters)
            roles = [record.get("role") for record in records] if records else []
            logger.debug(f"Roles for User '{uuid}': {roles}")
            return roles
        except Exception as e:
            logger.exception(f"Error retrieving roles for User '{uuid}': {str(e)}")
            raise e

    async def get_custom_accounts(self, uuid: str, tx: Optional[Any] = None) -> List[Dict[str, str]]:
        """Retrieve all custom accounts and roles for a user. Legacy; prefer get_smart_accounts."""
        query = """
        MATCH (u:User {uuid: $uuid})-[:HAS_CUSTOM_ACCOUNT|HAS_SMART_ACCOUNT]->(c)-[:HAS_ROLE]->(r:Role)
        RETURN DISTINCT c.address AS address, r.name AS role
        """
        parameters = {"uuid": uuid}
        try:
            if tx:
                logger.debug(f"Retrieving accounts and roles for User '{uuid}' within transaction.")
                result = await tx.run(query, parameters)
                records = [record.data() async for record in result]
            else:
                logger.debug(f"Retrieving accounts and roles for User '{uuid}'.")
                records = await self.query(query, parameters)
            custom_accounts = [{"address": record.get("address"), "role": record.get("role")} for record in records] if records else []
            logger.debug(f"Accounts for User '{uuid}': {custom_accounts}")
            return custom_accounts
        except Exception as e:
            logger.exception(f"Error retrieving accounts for User '{uuid}': {str(e)}")
            raise e

    async def get_smart_accounts(self, uuid: str, tx: Optional[Any] = None) -> List[Dict[str, str]]:
        """Retrieve all SMARTAccounts and roles for a user."""
        return await self.get_custom_accounts(uuid, tx)

    async def store_auth_token(self, uuid: str, token: str, expires_at: float, tx: Optional[Any] = None):
        """Store the authentication token with expiration for a user."""
        query = """
        MATCH (u:User {uuid: $uuid})
        SET u.auth_token = $token,
            u.auth_token_expires_at = $expires_at
        RETURN u
        """
        parameters = {
            "uuid": uuid,
            "token": token,
            "expires_at": expires_at
        }
        try:
            if tx:
                logger.debug(f"Storing auth token for UUID '{uuid}' within transaction.")
                await tx.run(query, parameters)
            else:
                logger.debug(f"Storing auth token for UUID '{uuid}'.")
                await self.execute(query, parameters)
            logger.info(f"Auth token stored for UUID '{uuid}' with expiration at '{expires_at}'.")
        except Exception as e:
            logger.exception(f"Error storing auth token for User '{uuid}': {str(e)}")
            raise e

    async def get_user_by_token(self, token: str, tx: Optional[Any] = None) -> Optional[Dict]:
        """Retrieve the user for a valid token, or None."""
        query = """
        MATCH (u:User {auth_token: $token})
        WHERE u.auth_token_expires_at > $current_time
        RETURN u.uuid AS uuid, u.roles AS roles
        """
        parameters = {"token": token, "current_time": time.time()}
        try:
            if tx:
                logger.debug(f"Retrieving User by token '{token}' within transaction.")
                result = await tx.run(query, parameters)
                records = [record.data() async for record in result]
            else:
                logger.debug(f"Retrieving User by token '{token}'.")
                records = await self.query(query, parameters)

            if records:
                user_data = records[0]
                logger.debug(f"User found for token '{token}': {user_data}")
                return user_data
            else:
                logger.debug(f"No User found or token '{token}' expired.")
                return None
        except Exception as e:
            logger.exception(f"Error retrieving User by token '{token}': {str(e)}")
            return None

    async def invalidate_token(self, token: str, tx: Optional[Any] = None):
        """Invalidate the authentication token after use or logout."""
        query = """
        MATCH (u:User {auth_token: $token})
        SET u.auth_token = NULL,
            u.auth_token_expires_at = NULL
        RETURN u
        """
        parameters = {"token": token}
        try:
            if tx:
                logger.debug(f"Invalidating auth token '{token}' within transaction.")
                await tx.run(query, parameters)
            else:
                logger.debug(f"Invalidating auth token '{token}'.")
                await self.execute(query, parameters)
            logger.info(f"Auth token '{token}' invalidated.")
        except Exception as e:
            logger.exception(f"Error invalidating auth token '{token}': {str(e)}")
            raise e

    async def log_model_card_upload(
        self,
        custom_account: str,
        token_id: int,
        storage_url: str,
        model_data: Dict[str, Any],
        tx: Optional[Any] = None
    ):
        """Log model card upload details in Neo4j, linking the ModelCard to the CustomAccount."""
        model_data = _alias_and_stub_model_data(model_data, relaxed=RELAX_SCHEMA)
        model_details = model_data.get("model_detail", {})
        quantitative_analysis = model_data.get("quantitative_analysis", {})
        qualitative_analysis = model_data.get("qualitative_analysis", {})
        model_snapshot = model_data.get("model_snapshot", {})
        model_architecture = model_data.get("model_architecture", {})
        usage = model_data.get("usage", {})
        model_creators = model_data.get("model_creators", {}).copy()
        system_type = model_data.get("system_type", {})
        implementation_frameworks = model_data.get("implementation_frameworks", {})
        compute_requirements = model_data.get("compute_requirements", {})
        model_characteristics = model_data.get("model_characteristics", {})
        data_overview = model_data.get("data_overview", {})
        evaluation_results = model_data.get("evaluation_results", {})
        subgroup_evaluation_results = model_data.get("subgroup_evaluation_results", [])
        fairness_evaluation_results = model_data.get("fairness_evaluation_results", {})
        model_usage_limitations = model_data.get("model_usage_limitations", {})
        terms_of_art = model_data.get("terms_of_art", [])
        reflections_on_model = model_data.get("reflections_on_model", [])
        authors = model_data.get("authors", [])

        model_creators_authors = model_creators.pop("authors", [])

        
        essential_sections = {
            "model_detail": model_details,
            "quantitative_analysis": quantitative_analysis,
            "qualitative_analysis": qualitative_analysis
        }

        missing = [name for name, data in essential_sections.items() if not data]
        if missing:
            if RELAX_SCHEMA:
                logger.warning(f"[RELAXED] Missing essential sections: {missing}. "
                            "Stubbing applied; proceeding.")
            else:
                for section_name in missing:
                    logger.error(f"{section_name} section is missing in model_data.")
                raise ValueError(f"{', '.join(missing)} section(s) are required in model_data.")


        query = """
        CALL apoc.do.when(
            $model_data_present,
            '
            MATCH (ca:CustomAccount {address: $custom_account})
            MERGE (m:ModelCard {token_id: $token_id})
            SET m.storage_url = $storage_url,
                m.uploaded_at = timestamp()
            MERGE (ca)-[:CREATED]->(m)
            
            // Create ModelDetail node and relationship
            MERGE (md:ModelDetail {model_id: $model_id})
            SET md.summary = $model_details.summary,
                md.motivation = $model_details.motivation,
                md.tasks = $model_details.tasks,
                md.use_cases = $model_details.use_cases,
                md.benefits = $model_details.benefits
            MERGE (m)-[:HAS_DETAILS]->(md)
            
            // Create QuantitativeAnalysis node and relationship
            MERGE (qa:QuantitativeAnalysis {token_id: $token_id})
            SET qa.accuracy = $quantitative_analysis.accuracy,
                qa.precision = $quantitative_analysis.precision
            MERGE (m)-[:HAS_QUANT_ANALYSIS]->(qa)
            
            // Create QualitativeAnalysis node and relationship
            MERGE (qla:QualitativeAnalysis {token_id: $token_id})
            SET qla.strengths = $qualitative_analysis.strengths,
                qla.weaknesses = $qualitative_analysis.weaknesses
            MERGE (m)-[:HAS_QUAL_ANALYSIS]->(qla)
            
            // Create ModelSnapshot node and relationship
            MERGE (ms:ModelSnapshot {token_id: $token_id})
            SET ms.snapshot_link = $model_snapshot.snapshot_link
            MERGE (m)-[:HAS_SNAPSHOT]->(ms)
            
            // Create ModelArchitecture node and relationship
            MERGE (ma:ModelArchitecture {token_id: $token_id})
            SET ma.description = $model_architecture.description,
                ma.input_specs = $model_architecture.input_specs,
                ma.output_specs = $model_architecture.output_specs
            MERGE (m)-[:HAS_ARCHITECTURE]->(ma)
            
            // Create Usage node and relationship
            MERGE (u:Usage {token_id: $token_id})
            SET u.applications = $usage.applications,
                u.benefits = $usage.benefits,
                u.known_caveats = $usage.known_caveats
            MERGE (m)-[:HAS_USAGE]->(u)
            
            // Create ModelCreators node and relationship
            MERGE (mc:ModelCreators {token_id: $token_id})
            SET mc.contact = $model_creators.contact,
                mc.citation = $model_creators.citation
            MERGE (m)-[:HAS_CREATORS]->(mc)
            
            // Create SystemType node and relationship
            MERGE (st:SystemType {token_id: $token_id})
            SET st.description = $system_type.description,
                st.upstream_dependencies = $system_type.upstream_dependencies,
                st.downstream_dependencies = $system_type.downstream_dependencies
            MERGE (m)-[:HAS_SYSTEM_TYPE]->(st)
            
            // Create ImplementationFrameworks node and relationship
            MERGE (ifw:ImplementationFrameworks {token_id: $token_id})
            SET ifw.training_hardware_software = $implementation_frameworks.training_hardware_software,
                ifw.deployment_hardware_software = $implementation_frameworks.deployment_hardware_software
            MERGE (m)-[:HAS_IMPLEMENTATION_FRAMEWORKS]->(ifw)
            
            // Create ComputeRequirements node and relationship
            MERGE (cr:ComputeRequirements {token_id: $token_id})
            SET cr.fine_tuning_chips = $compute_requirements.fine_tuning_chips,
                cr.fine_tuning_training_time_days = $compute_requirements.fine_tuning_training_time_days,
                cr.fine_tuning_total_computation = $compute_requirements.fine_tuning_total_computation,
                cr.fine_tuning_performance_tflops = $compute_requirements.fine_tuning_performance_tflops,
                cr.fine_tuning_energy_consumption_mwh = $compute_requirements.fine_tuning_energy_consumption_mwh,
                cr.inference_chips = $compute_requirements.inference_chips,
                cr.inference_training_time_days = $compute_requirements.inference_training_time_days,
                cr.inference_total_computation = $compute_requirements.inference_total_computation,
                cr.inference_performance_tflops = $compute_requirements.inference_performance_tflops,
                cr.inference_energy_consumption_mwh = $compute_requirements.inference_energy_consumption_mwh
            MERGE (m)-[:HAS_COMPUTE_REQUIREMENTS]->(cr)
            
            // Create ModelCharacteristics node and relationship
            MERGE (mcx:ModelCharacteristics {token_id: $token_id})
            SET mcx.initialization = $model_characteristics.initialization,
                mcx.status = $model_characteristics.status,
                mcx.stats = $model_characteristics.stats,
                mcx.training_epochs = $model_characteristics.training_epochs,
                mcx.dataset_name = $model_characteristics.dataset_name,
                mcx.size = $model_characteristics.size,
                mcx.version = $model_characteristics.version,
                mcx.weights = $model_characteristics.weights,
                mcx.layers = $model_characteristics.layers,
                mcx.loss = $model_characteristics.loss,
                mcx.update_cadence = $model_characteristics.update_cadence,
                mcx.latency = $model_characteristics.latency,
                mcx.pruning_is_pruned = $model_characteristics.pruning.is_pruned,
                mcx.pruning_sparsity_level = $model_characteristics.pruning.sparsity_level,
                mcx.quantization_is_quantized = $model_characteristics.quantization.is_quantized,
                mcx.quantization_bit_representation = $model_characteristics.quantization.bit_representation
            MERGE (m)-[:HAS_CHARACTERISTICS]->(mcx)
            
            // Create DataOverview node and relationship
            MERGE (do:DataOverview {token_id: $token_id})
            SET do.training_dataset_snapshot = $data_overview.training_dataset_snapshot,
                do.dataset_maintenance_versions = $data_overview.dataset_maintenance_versions,
                do.instrumentation = $data_overview.instrumentation,
                do.dataset_size = $data_overview.dataset_size,
                do.number_of_instances = $data_overview.number_of_instances,
                do.number_of_fields = $data_overview.number_of_fields,
                do.labeled_classes = $data_overview.labeled_classes,
                do.number_of_labels = $data_overview.number_of_labels,
                do.average_labels_per_instance = $data_overview.average_labels_per_instance,
                do.missing_labels = $data_overview.missing_labels,
                do.additional_notes = $data_overview.additional_notes,
                do.data_pre_processing = $data_overview.data_pre_processing,
                do.demographic_groups = $data_overview.demographic_groups,
                do.evaluation_data = $data_overview.evaluation_data
            MERGE (m)-[:HAS_DATA_OVERVIEW]->(do)
            
            // Create EvaluationResults node and relationship
            MERGE (er:EvaluationResults {token_id: $token_id})
            SET er.aggregate_evaluation_results = $evaluation_results.aggregate_evaluation_results,
                er.evaluation_process = $evaluation_results.evaluation_process,
                er.evaluation_results = $evaluation_results.evaluation_results
            MERGE (m)-[:HAS_EVALUATION_RESULTS]->(er)
            
            // Create FairnessEvaluationResults node and relationship
            MERGE (fer:FairnessEvaluationResults {token_id: $token_id})
            SET fer.fairness_criteria = $fairness_evaluation_results.fairness_criteria,
                fer.fairness_metrics_baseline = $fairness_evaluation_results.fairness_metrics_baseline,
                fer.fairness_results = $fairness_evaluation_results.fairness_results
            MERGE (m)-[:HAS_FAIRNESS_EVALUATION_RESULTS]->(fer)
            
            // Create ModelUsageLimitations node and relationship
            MERGE (mul:ModelUsageLimitations {token_id: $token_id})
            SET mul.sensitive_use = $model_usage_limitations.sensitive_use,
                mul.limitations = $model_usage_limitations.limitations,
                mul.ethical_considerations_risks = $model_usage_limitations.ethical_considerations_risks
            MERGE (m)-[:HAS_USAGE_LIMITATIONS]->(mul)
            
            // Insert WITH clause before UNWIND operations
            WITH m
            
            // Create Authors nodes and relationships
            UNWIND $authors AS author
                MERGE (a:Author {name: author.name, contact: author.contact})
                MERGE (m)-[:HAS_AUTHOR]->(a)
            
            // Insert WITH clause before next UNWIND
            WITH m
            
            // Create SubgroupEvaluationResults nodes and relationships
            UNWIND $subgroup_evaluation_results AS sub_er
                MERGE (ser:SubgroupEvaluationResults {subgroup_evaluated: sub_er.subgroup_evaluated})
                SET ser.evaluation_process_data = sub_er.evaluation_process_data,
                    ser.evaluation_results = sub_er.evaluation_results
                MERGE (m)-[:HAS_SUBGROUP_EVALUATION_RESULTS]->(ser)
            
            // Insert WITH clause before next UNWIND
            WITH m
            
            // Create TermsOfArt nodes and relationships
            UNWIND $terms_of_art AS term
                MERGE (toa:TermsOfArt {term: term.term})
                SET toa.definition = term.definition,
                    toa.source = term.source,
                    toa.interpretation = term.interpretation
                MERGE (m)-[:HAS_TERMS_OF_ART]->(toa)
            
            // Insert WITH clause before next UNWIND
            WITH m
            
            // Create ReflectionsOnModel nodes and relationships
            UNWIND $reflections_on_model AS reflection
                MERGE (rom:ReflectionsOnModel {title: reflection.title})
                SET rom.notes = reflection.notes
                MERGE (m)-[:HAS_REFLECTION]->(rom)
            
            ',
            '',
            {
                model_data_present: $model_data_present,
                custom_account: $custom_account,
                token_id: $token_id,
                storage_url: $storage_url,
                model_id: $model_id,
                model_details: $model_details,
                quantitative_analysis: $quantitative_analysis,
                qualitative_analysis: $qualitative_analysis,
                model_snapshot: $model_snapshot,
                model_architecture: $model_architecture,
                usage: $usage,
                model_creators: $model_creators,  
                system_type: $system_type,
                implementation_frameworks: $implementation_frameworks,
                compute_requirements: $compute_requirements,
                model_characteristics: $model_characteristics,
                data_overview: $data_overview,
                evaluation_results: $evaluation_results,
                fairness_evaluation_results: $fairness_evaluation_results,
                model_usage_limitations: $model_usage_limitations,
                authors: $authors,  
                subgroup_evaluation_results: $subgroup_evaluation_results,
                terms_of_art: $terms_of_art,
                reflections_on_model: $reflections_on_model
            }
        )
        YIELD value
        RETURN value
        """

        parameters = {
            "model_data_present": bool(model_data),
            "custom_account": custom_account,
            "token_id": token_id,
            "storage_url": storage_url,
            "model_id": model_details.get("model_id", token_id),  
            "model_details": model_details,
            "quantitative_analysis": quantitative_analysis,
            "qualitative_analysis": qualitative_analysis,
            "model_snapshot": model_snapshot,
            "model_architecture": model_architecture,
            "usage": usage,
            "model_creators": model_creators,  
            "system_type": system_type,
            "implementation_frameworks": implementation_frameworks,
            "compute_requirements": compute_requirements,
            "model_characteristics": model_characteristics,
            "data_overview": data_overview,
            "evaluation_results": evaluation_results,
            "fairness_evaluation_results": fairness_evaluation_results,
            "model_usage_limitations": model_usage_limitations,
            "authors": authors,  
            "subgroup_evaluation_results": subgroup_evaluation_results,
            "terms_of_art": terms_of_art,
            "reflections_on_model": reflections_on_model
        }

        try:
            if tx:
                logger.debug(
                    f"Logging model card upload for Token ID '{token_id}' by CustomAccount '{custom_account}' within transaction."
                )
                await tx.run(query, parameters)
            else:
                logger.debug(
                    f"Logging model card upload for Token ID '{token_id}' by CustomAccount '{custom_account}'."
                )
                await self.execute(query, parameters)
            logger.info(f"Model card upload logged in Neo4j for Token ID '{token_id}'.")
        except Neo4jError as e:
            logger.exception(
                f"Error logging model card upload for Token ID '{token_id}': {str(e)}"
            )
            raise e
        except ValueError as ve:
            logger.exception(
                f"Validation error during model card upload logging for Token ID '{token_id}': {str(ve)}"
            )
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as ex:
            logger.exception(
                f"Unexpected error during model card upload logging for Token ID '{token_id}': {str(ex)}"
            )
            raise HTTPException(status_code=500, detail="Internal server error")


    async def create_role_request(
        self,
        uuid: str,
        requested_role: str,
        reason: Optional[str] = None,
        tx: Optional[Any] = None
    ) -> str:
        """Create a role request for a user and return its request_id."""
        import secrets
        request_id = f"req_{secrets.token_hex(8)}"

        query = """
        MATCH (u:User {uuid: $uuid})
        CREATE (rr:RoleRequest {
            request_id: $request_id,
            requested_role: $requested_role,
            reason: $reason,
            status: 'pending',
            created_at: datetime(),
            updated_at: datetime()
        })
        CREATE (u)-[:HAS_ROLE_REQUEST]->(rr)
        RETURN rr.request_id AS request_id
        """
        parameters = {
            "uuid": uuid,
            "request_id": request_id,
            "requested_role": requested_role,
            "reason": reason or ""
        }
        try:
            if tx:
                await tx.run(query, parameters)
            else:
                await self.execute(query, parameters)
            logger.info(f"Created role request '{request_id}' for user '{uuid}'")
            return request_id
        except Exception as e:
            logger.exception(f"Error creating role request: {str(e)}")
            raise e

    async def get_user_role_requests(self, uuid: str, tx: Optional[Any] = None) -> List[Dict]:
        """Return this user's role-request history (all statuses), newest first."""
        query = """
        MATCH (u:User {uuid: $uuid})-[:HAS_ROLE_REQUEST]->(rr:RoleRequest)
        RETURN rr.request_id AS request_id,
               rr.requested_role AS requested_role,
               rr.reason AS reason,
               rr.status AS status,
               rr.admin_notes AS admin_notes,
               rr.created_at AS created_at,
               rr.updated_at AS updated_at
        ORDER BY rr.created_at DESC
        """
        try:
            if tx:
                result = await tx.run(query, {"uuid": uuid})
                records = [r.data() async for r in result]
            else:
                records = await self.query(query, {"uuid": uuid})
            return records
        except Exception as e:
            logger.exception(f"Error fetching role requests for user '{uuid}': {str(e)}")
            raise e

    async def has_pending_role_request(self, uuid: str, requested_role: str, tx: Optional[Any] = None) -> bool:
        """Returns True if the user already has a pending request for this role."""
        query = """
        MATCH (u:User {uuid: $uuid})-[:HAS_ROLE_REQUEST]->(rr:RoleRequest {status: 'pending', requested_role: $requested_role})
        RETURN count(rr) AS n
        """
        params = {"uuid": uuid, "requested_role": requested_role}
        try:
            if tx:
                result = await tx.run(query, params)
                records = [r.data() async for r in result]
            else:
                records = await self.query(query, params)
            return bool(records and records[0].get("n", 0) > 0)
        except Exception as e:
            logger.exception(f"Error checking pending role request: {str(e)}")
            raise e


    async def open_dispute_case(
        self,
        action_id: int,
        token_id: int,
        challenger_uuid: Optional[str],
        kind: str,
        tx: Optional[Any] = None,
    ) -> str:
        """Create a :DisputeCase for the action_id if absent (idempotent); returns the case_id."""
        case_id = f"dc_{kind}_{action_id}"
        query = """
        MERGE (dc:DisputeCase {case_id: $case_id})
        ON CREATE SET dc.action_id = $action_id,
                      dc.token_id = $token_id,
                      dc.kind = $kind,
                      dc.challenger_uuid = $challenger_uuid,
                      dc.status = 'open',
                      dc.created_at = timestamp()
        RETURN dc.case_id AS case_id
        """
        params = {
            "case_id": case_id,
            "action_id": int(action_id),
            "token_id": int(token_id),
            "kind": kind,
            "challenger_uuid": challenger_uuid,
        }
        try:
            if tx:
                await tx.run(query, params)
            else:
                await self.execute(query, params)
            return case_id
        except Exception as e:
            logger.exception(f"open_dispute_case failed: {str(e)}")
            raise e

    async def assign_panel_member(
        self,
        case_id: str,
        member_uuid: str,
        role_class: str,
        tx: Optional[Any] = None,
    ) -> bool:
        """Attach a panel member to an open dispute case; returns True if attached."""
        query = """
        MATCH (dc:DisputeCase {case_id: $case_id, status: 'open'})
        MATCH (u:User {uuid: $member_uuid})
        MERGE (dc)-[r:HAS_PANEL_MEMBER {role_class: $role_class}]->(u)
        ON CREATE SET r.assigned_at = timestamp()
        RETURN r IS NOT NULL AS attached
        """
        params = {"case_id": case_id, "member_uuid": member_uuid, "role_class": role_class}
        try:
            if tx:
                result = await tx.run(query, params)
                rows = [r.data() async for r in result]
            else:
                rows = await self.query(query, params)
            return bool(rows)
        except Exception as e:
            logger.exception(f"assign_panel_member failed: {str(e)}")
            raise e

    async def record_panel_vote(
        self,
        case_id: str,
        member_uuid: str,
        vote: str,
        signature: Optional[str] = None,
        signer_address: Optional[str] = None,
        tx: Optional[Any] = None,
    ) -> Optional[Dict]:
        """Record a panel member's vote and signature; returns the updated case state."""
        query = """
        MATCH (dc:DisputeCase {case_id: $case_id, status: 'open'})
              -[r:HAS_PANEL_MEMBER]->(u:User {uuid: $member_uuid})
        SET r.vote = $vote,
            r.voted_at = timestamp(),
            r.signature = coalesce($signature, r.signature),
            r.signer_address = coalesce($signer_address, r.signer_address)
        WITH dc
        OPTIONAL MATCH (dc)-[r2:HAS_PANEL_MEMBER]->(member:User)
        RETURN dc.case_id AS case_id, dc.action_id AS action_id, dc.kind AS kind,
               collect({
                 uuid: member.uuid,
                 role_class: r2.role_class,
                 vote: r2.vote,
                 voted_at: r2.voted_at,
                 signature: r2.signature,
                 signer_address: r2.signer_address
               }) AS panel
        """
        params = {
            "case_id": case_id, "member_uuid": member_uuid, "vote": vote,
            "signature": signature, "signer_address": signer_address,
        }
        try:
            if tx:
                result = await tx.run(query, params)
                rows = [r.data() async for r in result]
            else:
                rows = await self.query(query, params)
            return rows[0] if rows else None
        except Exception as e:
            logger.exception(f"record_panel_vote failed: {str(e)}")
            raise e

    async def close_dispute_case(
        self,
        case_id: str,
        outcome: str,
        tx: Optional[Any] = None,
    ) -> bool:
        query = """
        MATCH (dc:DisputeCase {case_id: $case_id})
        SET dc.status = 'closed', dc.outcome = $outcome, dc.closed_at = timestamp()
        RETURN dc.case_id AS case_id
        """
        params = {"case_id": case_id, "outcome": outcome}
        try:
            if tx:
                result = await tx.run(query, params)
                rows = [r.data() async for r in result]
            else:
                rows = await self.query(query, params)
            return bool(rows)
        except Exception as e:
            logger.exception(f"close_dispute_case failed: {str(e)}")
            raise e

    async def get_dispute_case(self, case_id: str, tx: Optional[Any] = None) -> Optional[Dict]:
        query = """
        MATCH (dc:DisputeCase {case_id: $case_id})
        OPTIONAL MATCH (dc)-[r:HAS_PANEL_MEMBER]->(u:User)
        RETURN dc.case_id AS case_id, dc.action_id AS action_id, dc.token_id AS token_id,
               dc.kind AS kind, dc.status AS status, dc.outcome AS outcome,
               dc.challenger_uuid AS challenger_uuid, dc.created_at AS created_at,
               dc.closed_at AS closed_at,
               collect({
                 uuid: u.uuid, username: u.username, eoa: u.eoa_address,
                 role_class: r.role_class, vote: r.vote,
                 assigned_at: r.assigned_at, voted_at: r.voted_at
               }) AS panel
        """
        try:
            if tx:
                result = await tx.run(query, {"case_id": case_id})
                rows = [r.data() async for r in result]
            else:
                rows = await self.query(query, {"case_id": case_id})
            return rows[0] if rows else None
        except Exception as e:
            logger.exception(f"get_dispute_case failed: {str(e)}")
            raise e

    async def get_eligible_arbiters(
        self,
        token_id: int,
        challenger_uuid: Optional[str],
        role_class: str,
        tx: Optional[Any] = None,
    ) -> List[Dict]:
        """Users qualified for a dispute panel for token_id, excluding creator, prior actors, and challenger."""
        actors_record = await self.get_card_actors(token_id, tx=tx)
        creator_uuid = actors_record.get("creator_uuid")
        prior_actor_uuids = []
        for ev in actors_record.get("events") or []:
            ev_actor = ev.get("actor")
            if ev_actor:
                u = await self.get_uuid_for_address(ev_actor, tx=tx)
                if u and u not in prior_actor_uuids:
                    prior_actor_uuids.append(u)

        excluded = set(filter(None, prior_actor_uuids + [creator_uuid, challenger_uuid]))

        query = """
        MATCH (u:User)-[:HAS_SMART_ACCOUNT]->(:SMARTAccount)-[:HAS_ROLE]->(r:Role {name: $role_class})
        WHERE NOT u.uuid IN $excluded
        RETURN DISTINCT u.uuid AS uuid, u.username AS username, u.eoa_address AS eoa
        ORDER BY u.uuid
        """
        params = {"role_class": role_class, "excluded": list(excluded)}
        try:
            if tx:
                result = await tx.run(query, params)
                rows = [r.data() async for r in result]
            else:
                rows = await self.query(query, params)
        except Exception as e:
            logger.exception(f"get_eligible_arbiters failed: {str(e)}")
            raise e

        from app.utils.identity_binding import (
            ROLE_TO_CLAIM_TYPES,
            get_claim_status,
        )
        claim_types = ROLE_TO_CLAIM_TYPES.get(role_class, [])
        if not claim_types:
            return rows
        eligible = []
        for row in rows:
            eoa = row.get("eoa")
            if not eoa:
                continue
            try:
                status = get_claim_status(eoa, claim_types[0])
                if (
                    status.get("has_claim")
                    and status.get("attestation_level") == "institutional"
                ):
                    eligible.append(row)
            except Exception as exc:
                logger.debug(f"claim check failed for {eoa}: {exc}")
        return eligible

    async def get_uuid_for_address(self, address: str, tx: Optional[Any] = None) -> Optional[str]:
        """Reverse lookup: return the UUID owning any address (EOA or SMART account)."""
        if not address:
            return None
        addr_lc = address.lower()
        query = """
        MATCH (u:User)
        WHERE toLower(u.eoa_address) = $addr
        RETURN u.uuid AS uuid
        UNION
        MATCH (u:User)-[:HAS_CUSTOM_ACCOUNT|HAS_SMART_ACCOUNT]->(c)
        WHERE toLower(c.address) = $addr
        RETURN u.uuid AS uuid
        """
        try:
            if tx:
                result = await tx.run(query, {"addr": addr_lc})
                rows = [r.data() async for r in result]
            else:
                rows = await self.query(query, {"addr": addr_lc})
            return rows[0]["uuid"] if rows else None
        except Exception as e:
            logger.exception(f"get_uuid_for_address failed for {address}: {str(e)}")
            return None

    async def get_card_actors(self, token_id: int, tx: Optional[Any] = None) -> Dict[str, Any]:
        """Return the people involved in a card's lifecycle so far (for the SoD guard)."""
        query = """
        MATCH (mc:ModelCard {token_id: $token_id})
        OPTIONAL MATCH (mc)-[:HAS_EVENT]->(e:StatusEvent)
        WITH mc, collect({action: e.action, actor: e.actor, timestamp: e.timestamp}) AS events
        RETURN mc.creator_uuid AS creator_uuid,
               mc.developer_address AS developer_address,
               events
        """
        try:
            if tx:
                result = await tx.run(query, {"token_id": int(token_id)})
                rows = [r.data() async for r in result]
            else:
                rows = await self.query(query, {"token_id": int(token_id)})
            return rows[0] if rows else {"creator_uuid": None, "events": []}
        except Exception as e:
            logger.exception(f"get_card_actors failed for token {token_id}: {str(e)}")
            return {"creator_uuid": None, "events": []}

    async def get_pending_role_requests(self, tx: Optional[Any] = None) -> List[Dict]:
        """Get all pending role requests."""
        query = """
        MATCH (u:User)-[:HAS_ROLE_REQUEST]->(rr:RoleRequest {status: 'pending'})
        RETURN rr.request_id AS request_id,
               u.uuid AS uuid,
               u.eoa_address AS eoa_address,
               u.luceid AS luceid,
               rr.requested_role AS requested_role,
               rr.reason AS reason,
               rr.created_at AS created_at
        ORDER BY rr.created_at DESC
        """
        try:
            if tx:
                result = await tx.run(query)
                records = [record.data() async for record in result]
            else:
                records = await self.query(query)
            return records
        except Exception as e:
            logger.exception(f"Error fetching pending role requests: {str(e)}")
            raise e

    async def get_role_request(self, request_id: str, tx: Optional[Any] = None) -> Optional[Dict]:
        """Get a specific role request by ID."""
        query = """
        MATCH (u:User)-[:HAS_ROLE_REQUEST]->(rr:RoleRequest {request_id: $request_id})
        RETURN rr.request_id AS request_id,
               u.uuid AS uuid,
               u.eoa_address AS eoa_address,
               u.luceid AS luceid,
               rr.requested_role AS requested_role,
               rr.reason AS reason,
               rr.status AS status,
               rr.created_at AS created_at
        """
        parameters = {"request_id": request_id}
        try:
            if tx:
                result = await tx.run(query, parameters)
                records = [record.data() async for record in result]
            else:
                records = await self.query(query, parameters)
            return records[0] if records else None
        except Exception as e:
            logger.exception(f"Error fetching role request: {str(e)}")
            raise e

    async def update_role_request_status(
        self,
        request_id: str,
        status: str,
        admin_notes: Optional[str] = None,
        tx: Optional[Any] = None
    ):
        """Update the status of a role request."""
        query = """
        MATCH (rr:RoleRequest {request_id: $request_id})
        SET rr.status = $status,
            rr.admin_notes = $admin_notes,
            rr.updated_at = datetime()
        """
        parameters = {
            "request_id": request_id,
            "status": status,
            "admin_notes": admin_notes or ""
        }
        try:
            if tx:
                await tx.run(query, parameters)
            else:
                await self.execute(query, parameters)
            logger.info(f"Updated role request '{request_id}' to status '{status}'")
        except Exception as e:
            logger.exception(f"Error updating role request status: {str(e)}")
            raise e

    async def get_all_users_with_roles(self, tx: Optional[Any] = None) -> List[Dict]:
        """Get all users with their roles for the admin dashboard."""
        query = """
        MATCH (u:User)
        OPTIONAL MATCH (u)-[:HAS_CUSTOM_ACCOUNT]->(ca:CustomAccount)-[:HAS_ROLE]->(r:Role)
        RETURN u.uuid AS uuid,
               u.eoa_address AS eoa_address,
               u.luceid AS luceid,
               u.verified AS verified,
               collect(DISTINCT r.name) AS roles
        ORDER BY u.uuid
        """
        try:
            if tx:
                result = await tx.run(query)
                records = [record.data() async for record in result]
            else:
                records = await self.query(query)
            return records
        except Exception as e:
            logger.exception(f"Error fetching all users: {str(e)}")
            raise e

    async def get_platform_stats(self, tx: Optional[Any] = None) -> Dict:
        """Get platform statistics for the admin dashboard."""
        query = """
        MATCH (u:User)
        WITH count(u) AS total_users
        OPTIONAL MATCH (mc:ModelCard)
        WITH total_users, count(mc) AS total_model_cards
        OPTIONAL MATCH (rr:RoleRequest {status: 'pending'})
        WITH total_users, total_model_cards, count(rr) AS pending_requests
        OPTIONAL MATCH (ca:CustomAccount)-[:HAS_ROLE]->(r:Role)
        WITH total_users, total_model_cards, pending_requests, r.name AS role, count(ca) AS count
        RETURN total_users, total_model_cards, pending_requests, collect({role: role, count: count}) AS role_distribution
        """
        try:
            if tx:
                result = await tx.run(query)
                records = [record.data() async for record in result]
            else:
                records = await self.query(query)

            if records:
                data = records[0]
                return {
                    "total_users": data.get("total_users", 0),
                    "total_model_cards": data.get("total_model_cards", 0),
                    "pending_role_requests": data.get("pending_requests", 0),
                    "role_distribution": data.get("role_distribution", [])
                }
            return {
                "total_users": 0,
                "total_model_cards": 0,
                "pending_role_requests": 0,
                "role_distribution": []
            }
        except Exception as e:
            logger.exception(f"Error fetching platform stats: {str(e)}")
            raise e


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

neo4j_conn = Neo4jConnection(uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD)









