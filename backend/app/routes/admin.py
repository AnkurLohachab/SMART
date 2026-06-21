"""Admin routes for role management and approval workflows."""

from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Any
import logging
import json
import os
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from app.db import neo4j_conn
from app.utils import smart_chain

try:
    from neo4j.time import DateTime as Neo4jDateTime, Date as Neo4jDate, Time as Neo4jTime, Duration as Neo4jDuration
except ImportError:
    Neo4jDateTime = Neo4jDate = Neo4jTime = Neo4jDuration = None

try:
    from jose import jwt, JWTError
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    jwt = None
    JWTError = Exception

logger = logging.getLogger("backend.admin")
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBearer(auto_error=False)

def serialize_neo4j_data(data: Any) -> Any:
    """Serialize Neo4j data types to JSON-compatible formats"""
    if data is None:
        return None

    if Neo4jDateTime and isinstance(data, Neo4jDateTime):
        return data.isoformat()
    if Neo4jDate and isinstance(data, Neo4jDate):
        return data.isoformat()
    if Neo4jTime and isinstance(data, Neo4jTime):
        return data.isoformat()
    if Neo4jDuration and isinstance(data, Neo4jDuration):
        return str(data)

    if hasattr(data, 'isoformat'):
        return data.isoformat()

    if isinstance(data, dict):
        return {k: serialize_neo4j_data(v) for k, v in data.items()}
    if isinstance(data, list):
        return [serialize_neo4j_data(item) for item in data]

    type_name = type(data).__name__
    if 'neo4j' in type(data).__module__.lower() if hasattr(type(data), '__module__') else False:
        try:
            return str(data)
        except:
            return repr(data)

    return data

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

_DEFAULT_DEMO_PASSWORD = "admin123"

def _hash_password(password: str) -> str:
    """Hash password using SHA-256 (for demo). In production, use bcrypt."""
    return hashlib.sha256(password.encode()).hexdigest()

def _verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash."""
    return _hash_password(password) == password_hash

def _get_admin_password_hash() -> str:
    """Get admin password hash, using default for demo if not configured."""
    if ADMIN_PASSWORD_HASH:
        return ADMIN_PASSWORD_HASH
    logger.warning("ADMIN_PASSWORD_HASH not set - using default demo credentials (NOT FOR PRODUCTION)")
    return _hash_password(_DEFAULT_DEMO_PASSWORD)

def _create_jwt_token(username: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT token for admin authentication."""
    if not JWT_AVAILABLE:
        raise HTTPException(status_code=500, detail="JWT library not available")

    expire = datetime.utcnow() + (expires_delta or timedelta(hours=JWT_EXPIRATION_HOURS))
    payload = {
        "sub": username,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "admin_access"
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def _verify_jwt_token(token: str) -> Optional[dict]:
    """Verify JWT token and return payload if valid."""
    if not JWT_AVAILABLE:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "admin_access":
            return None
        return payload
    except JWTError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None
    except Exception as e:
        logger.warning(f"JWT verification error: {e}")
        return None

async def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Dependency to verify admin JWT token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    payload = _verify_jwt_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload.get("sub", "admin")


class AdminLoginRequest(BaseModel):
    username: str
    password: str

class RoleRequestCreate(BaseModel):
    uuid: str
    requested_role: str
    reason: Optional[str] = None

class RoleApprovalRequest(BaseModel):
    request_id: str
    approved: bool
    admin_notes: Optional[str] = None


@router.post("/login")
async def admin_login(request: AdminLoginRequest):
    """Admin login; returns a signed JWT on valid credentials."""
    if request.username != ADMIN_USERNAME:
        logger.warning(f"Failed admin login attempt for username: {request.username}")
        raise HTTPException(status_code=401, detail="Invalid admin credentials")

    expected_hash = _get_admin_password_hash()
    if not _verify_password(request.password, expected_hash):
        logger.warning(f"Failed admin login attempt - invalid password for: {request.username}")
        raise HTTPException(status_code=401, detail="Invalid admin credentials")

    try:
        token = _create_jwt_token(request.username)
        logger.info(f"Admin login successful for: {request.username}")

        return JSONResponse(content={
            "message": "Admin login successful",
            "token": token,
            "role": "Admin",
            "expires_in_hours": JWT_EXPIRATION_HOURS
        })
    except Exception as e:
        logger.error(f"Failed to generate JWT token: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate authentication token")


@router.post("/role-requests")
async def create_role_request(request: RoleRequestCreate):
    """Submit a request for the Reviewer or Publisher role (legacy "Authenticator" maps to "Reviewer")."""
    try:
        if request.requested_role == "Authenticator":
            request.requested_role = "Reviewer"

        if request.requested_role not in ["Reviewer", "Publisher"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid role. Only 'Reviewer' or 'Publisher' can be requested."
            )

        user = await neo4j_conn.get_user_by_uuid(request.uuid)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        existing_roles = await neo4j_conn.get_user_roles(request.uuid)
        if request.requested_role in existing_roles:
            raise HTTPException(
                status_code=400,
                detail=f"User already has the {request.requested_role} role"
            )

        if await neo4j_conn.has_pending_role_request(request.uuid, request.requested_role):
            raise HTTPException(
                status_code=400,
                detail=f"You already have a pending {request.requested_role} request awaiting review"
            )

        request_id = await neo4j_conn.create_role_request(
            uuid=request.uuid,
            requested_role=request.requested_role,
            reason=request.reason
        )

        return JSONResponse(content={
            "message": "Role request submitted successfully",
            "request_id": request_id,
            "status": "pending"
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating role request: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create role request")

@router.get("/role-requests")
async def get_pending_role_requests(admin: str = Depends(verify_admin_token)):
    """Get all pending role requests (admin only)."""
    try:
        requests = await neo4j_conn.get_pending_role_requests()
        serialized_requests = []
        for req in requests:
            serialized_req = {}
            for key, value in req.items():
                if hasattr(value, 'isoformat'):
                    serialized_req[key] = value.isoformat()
                elif hasattr(value, 'to_native'):
                    serialized_req[key] = str(value.to_native())
                elif value is not None and 'neo4j' in str(type(value).__module__):
                    serialized_req[key] = str(value)
                else:
                    serialized_req[key] = value
            serialized_requests.append(serialized_req)

        return JSONResponse(content={
            "requests": serialized_requests,
            "count": len(serialized_requests)
        })
    except Exception as e:
        logger.exception(f"Error fetching role requests: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch role requests")

@router.post("/role-requests/{request_id}/approve")
async def approve_role_request(request_id: str, approval: RoleApprovalRequest, admin: str = Depends(verify_admin_token)):
    """Approve or reject a role request (admin only); on approval creates the role account."""
    try:
        role_request = await neo4j_conn.get_role_request(request_id)
        if not role_request:
            raise HTTPException(status_code=404, detail="Role request not found")

        if role_request.get("status") != "pending":
            raise HTTPException(status_code=400, detail="Role request has already been processed")

        uuid = role_request.get("uuid")
        requested_role = role_request.get("requested_role")

        if approval.approved:
            user = await neo4j_conn.get_user_by_uuid(uuid)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            eoa_address = user.get("eoa_address")
            smart_id = user.get("smart_id") or user.get("luceid")

            role_mapping = {
                "Reviewer": 2,
                "Authenticator": 2,
                "Publisher": 3,
            }
            role_value = role_mapping.get(requested_role)

            if role_value is None:
                raise HTTPException(status_code=400, detail="Invalid role mapping")

            try:
                new_account_address = await smart_chain.create_single_account_gasless(
                    eoa_address, smart_id, role_value
                )

                await neo4j_conn.store_custom_account(uuid, new_account_address, requested_role)

                logger.info(f"Created {requested_role} account for user {uuid}: {new_account_address}")

                try:
                    from app.utils.identity_binding import (
                        issue_self_attested_claims_for_role,
                    )
                    claim_results = issue_self_attested_claims_for_role(eoa_address, requested_role)
                    logger.info(
                        f"Issued self-attested claim(s) for user {uuid} role {requested_role}: {claim_results}"
                    )
                except Exception as claim_err:
                    logger.warning(
                        f"Self-attested claim issuance failed for user {uuid} role {requested_role}: {claim_err}"
                    )

            except Exception as blockchain_error:
                logger.error(f"Blockchain error creating account: {blockchain_error}")
                await neo4j_conn.update_role_request_status(
                    request_id,
                    "approved_pending_blockchain",
                    approval.admin_notes
                )
                return JSONResponse(content={
                    "message": "Role approved but blockchain account creation failed. Will retry.",
                    "status": "approved_pending_blockchain"
                })

        new_status = "approved" if approval.approved else "rejected"
        await neo4j_conn.update_role_request_status(request_id, new_status, approval.admin_notes)

        return JSONResponse(content={
            "message": f"Role request {new_status}",
            "request_id": request_id,
            "status": new_status,
            "role": requested_role if approval.approved else None
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing role approval: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process role approval")

@router.get("/role-requests/failed")
async def get_failed_role_requests(admin: str = Depends(verify_admin_token)):
    """Get role requests that failed blockchain account creation."""
    try:
        query = """
        MATCH (u:User)-[:HAS_ROLE_REQUEST]->(rr:RoleRequest)
        WHERE rr.status = 'approved_pending_blockchain'
        RETURN rr.request_id AS request_id,
               u.uuid AS uuid,
               u.eoa_address AS eoa_address,
               COALESCE(u.smart_id, u.luceid) AS smart_id,
               rr.requested_role AS requested_role,
               rr.reason AS reason,
               rr.created_at AS created_at,
               rr.updated_at AS updated_at
        ORDER BY rr.updated_at DESC
        """
        results = await neo4j_conn.query(query)
        serialized = []
        for req in results:
            serialized_req = {}
            for key, value in req.items():
                if hasattr(value, 'isoformat'):
                    serialized_req[key] = value.isoformat()
                elif value is not None and 'neo4j' in str(type(value).__module__):
                    serialized_req[key] = str(value)
                else:
                    serialized_req[key] = value
            serialized.append(serialized_req)

        return JSONResponse(content={
            "requests": serialized,
            "count": len(serialized)
        })
    except Exception as e:
        logger.exception(f"Error fetching failed role requests: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch failed role requests")

@router.post("/role-requests/{request_id}/retry")
async def retry_role_request(request_id: str, admin: str = Depends(verify_admin_token)):
    """Retry blockchain account creation for a failed role request."""
    try:
        role_request = await neo4j_conn.get_role_request(request_id)
        if not role_request:
            raise HTTPException(status_code=404, detail="Role request not found")

        if role_request.get("status") != "approved_pending_blockchain":
            raise HTTPException(status_code=400, detail="Role request is not in retry-able state")

        uuid = role_request.get("uuid")
        requested_role = role_request.get("requested_role")

        user = await neo4j_conn.get_user_by_uuid(uuid)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        eoa_address = user.get("eoa_address")
        smart_id = user.get("smart_id") or user.get("luceid")

        role_mapping = {
            "Reviewer": 2,
            "Authenticator": 2,
            "Publisher": 3,
        }
        role_value = role_mapping.get(requested_role)

        if role_value is None:
            raise HTTPException(status_code=400, detail="Invalid role mapping")

        try:
            new_account_address = await smart_chain.create_single_account_gasless(
                eoa_address, smart_id, role_value
            )

            await neo4j_conn.store_custom_account(uuid, new_account_address, requested_role)

            await neo4j_conn.update_role_request_status(request_id, "approved", "Retry successful")

            logger.info(f"Retry successful: Created {requested_role} account for user {uuid}: {new_account_address}")

            return JSONResponse(content={
                "message": "Blockchain account created successfully",
                "status": "approved",
                "account_address": new_account_address,
                "role": requested_role
            })

        except Exception as blockchain_error:
            logger.error(f"Retry failed - Blockchain error: {blockchain_error}")
            raise HTTPException(status_code=500, detail=f"Blockchain error: {str(blockchain_error)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error retrying role request: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retry role request")

@router.get("/users")
async def get_all_users(admin: str = Depends(verify_admin_token)):
    """Get all registered users with their roles (admin only)."""
    try:
        users = await neo4j_conn.get_all_users_with_roles()
        serialized_users = serialize_neo4j_data(users)
        return JSONResponse(content={
            "users": serialized_users,
            "count": len(serialized_users)
        })
    except Exception as e:
        logger.exception(f"Error fetching users: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")

@router.get("/stats")
async def get_admin_stats(admin: str = Depends(verify_admin_token)):
    """Get platform statistics for the admin dashboard."""
    try:
        stats = await neo4j_conn.get_platform_stats()
        return JSONResponse(content=serialize_neo4j_data(stats))
    except Exception as e:
        logger.exception(f"Error fetching stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch statistics")

@router.get("/neo4j/query")
async def run_neo4j_query(query: str, limit: int = 100, admin: str = Depends(verify_admin_token)):
    """Run a read-only (MATCH-only) Cypher query on Neo4j (admin only)."""
    try:
        query_upper = query.strip().upper()
        if not query_upper.startswith("MATCH"):
            raise HTTPException(
                status_code=400,
                detail="Only MATCH (read) queries are allowed"
            )

        if "LIMIT" not in query_upper:
            query = f"{query} LIMIT {limit}"

        results = await neo4j_conn.query(query)
        serialized_results = serialize_neo4j_data(results)

        return JSONResponse(content={
            "results": serialized_results,
            "count": len(serialized_results),
            "query": query
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error running Neo4j query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@router.get("/neo4j/schema")
async def get_neo4j_schema(admin: str = Depends(verify_admin_token)):
    """Get a Neo4j database schema overview."""
    try:
        labels_query = "CALL db.labels() YIELD label RETURN label"
        labels = await neo4j_conn.query(labels_query)

        rel_query = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
        relationships = await neo4j_conn.query(rel_query)

        counts = {}
        for label_record in labels:
            label = label_record.get('label')
            count_query = f"MATCH (n:{label}) RETURN count(n) as count"
            count_result = await neo4j_conn.query(count_query)
            counts[label] = count_result[0].get('count', 0) if count_result else 0

        return JSONResponse(content={
            "labels": [r.get('label') for r in labels],
            "relationships": [r.get('relationshipType') for r in relationships],
            "node_counts": counts
        })
    except Exception as e:
        logger.exception(f"Error fetching Neo4j schema: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch schema")

@router.get("/minio/buckets")
async def get_minio_buckets(admin: str = Depends(verify_admin_token)):
    """Get MinIO buckets and their object counts."""
    try:
        from app.utils.minio_utils import minio_client

        buckets = []
        for bucket in minio_client.list_buckets():
            objects = list(minio_client.list_objects(bucket.name, recursive=True))
            buckets.append({
                "name": bucket.name,
                "creation_date": bucket.creation_date.isoformat() if bucket.creation_date else None,
                "object_count": len(objects)
            })

        return JSONResponse(content={
            "buckets": buckets,
            "count": len(buckets)
        })
    except Exception as e:
        logger.exception(f"Error fetching MinIO buckets: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch buckets")

@router.get("/minio/objects/{bucket_name}")
async def get_minio_objects(bucket_name: str, prefix: str = "", limit: int = 100, admin: str = Depends(verify_admin_token)):
    """Get objects in a MinIO bucket."""
    try:
        from app.utils.minio_utils import minio_client

        objects = []
        count = 0
        for obj in minio_client.list_objects(bucket_name, prefix=prefix, recursive=True):
            if count >= limit:
                break
            objects.append({
                "name": obj.object_name,
                "size": obj.size,
                "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                "etag": obj.etag,
                "content_type": obj.content_type
            })
            count += 1

        return JSONResponse(content={
            "bucket": bucket_name,
            "objects": objects,
            "count": len(objects)
        })
    except Exception as e:
        logger.exception(f"Error fetching MinIO objects: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch objects")

@router.get("/minio/object/{bucket_name}/{object_path:path}")
async def get_minio_object_content(bucket_name: str, object_path: str, admin: str = Depends(verify_admin_token)):
    """Get the content of a specific object (JSON/text files)."""
    try:
        from app.utils.minio_utils import minio_client

        response = minio_client.get_object(bucket_name, object_path)
        content = response.read().decode('utf-8')
        response.close()
        response.release_conn()

        try:
            content = json.loads(content)
        except:
            pass

        return JSONResponse(content={
            "bucket": bucket_name,
            "path": object_path,
            "content": content
        })
    except Exception as e:
        logger.exception(f"Error fetching MinIO object: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch object")

@router.get("/model-cards")
async def get_all_model_cards(admin: str = Depends(verify_admin_token)):
    """Get all model cards with detailed info (admin only)."""
    try:
        query = """
        MATCH (mc:ModelCard)
        OPTIONAL MATCH (mc)-[:HAS_EVENT]->(event:StatusEvent)
        RETURN mc.token_id AS token_id,
               mc.model_name AS model_name,
               mc.current_status AS status,
               mc.created_at AS created_at,
               mc.version AS version,
               mc.developer_organization AS organization,
               mc.blockchain_address AS creator,
               count(event) AS event_count
        ORDER BY mc.token_id DESC
        """
        results = await neo4j_conn.query(query)
        serialized = serialize_neo4j_data(results)

        return JSONResponse(content={
            "model_cards": serialized,
            "count": len(serialized)
        })
    except Exception as e:
        logger.exception(f"Error fetching model cards: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch model cards")

@router.get("/blockchain/status")
async def get_blockchain_status(admin: str = Depends(verify_admin_token)):
    """Get blockchain connection status and info."""
    try:
        from web3 import Web3
        import os

        WEB3_PROVIDER_URL = os.getenv("WEB3_PROVIDER_URL", "http://hardhat:8545")
        w3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER_URL))

        return JSONResponse(content={
            "connected": w3.is_connected(),
            "chain_id": w3.eth.chain_id if w3.is_connected() else None,
            "block_number": w3.eth.block_number if w3.is_connected() else None,
            "gas_price": str(w3.eth.gas_price) if w3.is_connected() else None,
            "provider": WEB3_PROVIDER_URL
        })
    except Exception as e:
        logger.exception(f"Error fetching blockchain status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch blockchain status")


@router.get("/explorer/contracts")
async def get_deployed_contracts(admin: str = Depends(verify_admin_token)):
    """Get information about deployed smart contracts."""
    try:
        from web3 import Web3
        import os

        WEB3_PROVIDER_URL = os.getenv("WEB3_PROVIDER_URL", "http://hardhat:8545")
        w3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER_URL))

        contracts = [
            {
                "name": "SMARTAccountFactory",
                "address": os.getenv("SMART_ACCOUNT_FACTORY_ADDRESS") or os.getenv("CONTRACT_ADDRESS", ""),
                "description": "Factory contract for creating SMART accounts (EIP-4337)",
                "type": "Factory"
            },
            {
                "name": "SMARTRelayer",
                "address": os.getenv("SMART_RELAYER_ADDRESS") or os.getenv("GASLESS_RELAYER_ADDRESS", ""),
                "description": "Relayer contract for gasless meta-transactions",
                "type": "Relayer"
            },
            {
                "name": "SMARTLifecycle",
                "address": os.getenv("SMART_LIFECYCLE_ADDRESS") or os.getenv("MLUCE_ADDRESS", ""),
                "description": "Model Card Lifecycle FSM (ERC-721 + EIP-5192)",
                "type": "NFT Registry"
            },
            {
                "name": "SMARTIdentityRegistry",
                "address": os.getenv("SMART_IDENTITY_REGISTRY_ADDRESS", ""),
                "description": "Identity and claims registry for SMART users",
                "type": "Identity"
            }
        ]

        for contract in contracts:
            if contract["address"] and w3.is_connected():
                try:
                    balance = w3.eth.get_balance(contract["address"])
                    contract["balance"] = str(w3.from_wei(balance, 'ether'))
                except:
                    contract["balance"] = "0"

        return JSONResponse(content={"contracts": contracts})
    except Exception as e:
        logger.exception(f"Error fetching contracts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch contracts")

@router.get("/explorer/transactions")
async def get_recent_transactions(limit: int = 50, admin: str = Depends(verify_admin_token)):
    """Get recent transactions from status events."""
    try:
        query = """
        MATCH (mc:ModelCard)-[:HAS_EVENT]->(e:StatusEvent)
        RETURN mc.token_id AS token_id,
               mc.model_name AS model_name,
               e.event_type AS event_type,
               e.timestamp AS timestamp,
               e.tx_hash AS tx_hash,
               e.actor AS actor,
               e.new_status AS new_status,
               e.previous_status AS previous_status
        ORDER BY e.timestamp DESC
        LIMIT $limit
        """
        results = await neo4j_conn.query(query, {"limit": limit})
        serialized = serialize_neo4j_data(results)

        return JSONResponse(content={
            "transactions": serialized,
            "count": len(serialized)
        })
    except Exception as e:
        logger.exception(f"Error fetching transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch transactions")

@router.get("/explorer/blocks")
async def get_recent_blocks(limit: int = 10, admin: str = Depends(verify_admin_token)):
    """Get recent blocks from the blockchain."""
    try:
        from web3 import Web3
        import os

        WEB3_PROVIDER_URL = os.getenv("WEB3_PROVIDER_URL", "http://hardhat:8545")
        w3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER_URL))

        if not w3.is_connected():
            raise HTTPException(status_code=503, detail="Blockchain not connected")

        latest_block = w3.eth.block_number
        blocks = []

        for i in range(min(limit, latest_block + 1)):
            block_num = latest_block - i
            if block_num < 0:
                break
            block = w3.eth.get_block(block_num)
            blocks.append({
                "number": block.number,
                "hash": block.hash.hex() if block.hash else "",
                "timestamp": block.timestamp,
                "transactions": len(block.transactions),
                "gas_used": block.gasUsed,
                "gas_limit": block.gasLimit,
                "miner": block.miner if hasattr(block, 'miner') else ""
            })

        return JSONResponse(content={
            "blocks": blocks,
            "latest_block": latest_block
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching blocks: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch blocks")

@router.get("/explorer/accounts")
async def get_all_accounts(admin: str = Depends(verify_admin_token)):
    """Get all SMART accounts with their roles and users (CustomAccount and SMARTAccount labels)."""
    try:
        query = """
        MATCH (u:User)-[rel:HAS_CUSTOM_ACCOUNT|HAS_SMART_ACCOUNT]->(ca)-[:HAS_ROLE]->(r:Role)
        WHERE ca:CustomAccount OR ca:SMARTAccount
        RETURN u.uuid AS user_uuid,
               u.eoa_address AS eoa_address,
               COALESCE(u.smart_id, u.luceid) AS smart_id,
               ca.address AS account_address,
               r.name AS role,
               ca.created_at AS created_at
        ORDER BY ca.created_at DESC
        """
        results = await neo4j_conn.query(query)
        serialized = serialize_neo4j_data(results)

        return JSONResponse(content={
            "accounts": serialized,
            "count": len(serialized)
        })
    except Exception as e:
        logger.exception(f"Error fetching accounts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch accounts")

@router.get("/explorer/stats")
async def get_explorer_stats(admin: str = Depends(verify_admin_token)):
    """Get platform statistics for the explorer dashboard."""
    try:
        from web3 import Web3
        import os

        WEB3_PROVIDER_URL = os.getenv("WEB3_PROVIDER_URL", "http://hardhat:8545")
        w3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER_URL))

        stats_query = """
        MATCH (u:User) WITH count(u) AS total_users
        OPTIONAL MATCH (ca) WHERE ca:CustomAccount OR ca:SMARTAccount
        WITH total_users, count(ca) AS total_accounts
        OPTIONAL MATCH (mc:ModelCard)
        WITH total_users, total_accounts, count(mc) AS total_model_cards
        OPTIONAL MATCH (e:StatusEvent)
        WITH total_users, total_accounts, total_model_cards, count(e) AS total_events
        RETURN total_users, total_accounts, total_model_cards, total_events
        """
        stats_result = await neo4j_conn.query(stats_query)

        role_query = """
        MATCH (ca)-[:HAS_ROLE]->(r:Role)
        WHERE ca:CustomAccount OR ca:SMARTAccount
        RETURN r.name AS role, count(ca) AS count
        ORDER BY count DESC
        """
        role_result = await neo4j_conn.query(role_query)

        status_query = """
        MATCH (mc:ModelCard)
        RETURN mc.current_status AS status, count(mc) AS count
        """
        status_result = await neo4j_conn.query(status_query)

        blockchain_stats = {}
        if w3.is_connected():
            blockchain_stats = {
                "block_number": w3.eth.block_number,
                "chain_id": w3.eth.chain_id,
                "gas_price_gwei": float(w3.from_wei(w3.eth.gas_price, 'gwei'))
            }

        neo4j_stats = stats_result[0] if stats_result else {}

        return JSONResponse(content={
            "platform": {
                "total_users": neo4j_stats.get("total_users", 0),
                "total_accounts": neo4j_stats.get("total_accounts", 0),
                "total_model_cards": neo4j_stats.get("total_model_cards", 0),
                "total_events": neo4j_stats.get("total_events", 0)
            },
            "role_distribution": role_result,
            "model_card_status": status_result,
            "blockchain": blockchain_stats
        })
    except Exception as e:
        logger.exception(f"Error fetching explorer stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch stats")

@router.get("/explorer/model-cards/csv")
async def export_model_cards_csv(admin: str = Depends(verify_admin_token)):
    """Export all model cards as CSV."""
    try:
        import csv
        import io

        query = """
        MATCH (mc:ModelCard)
        OPTIONAL MATCH (mc)-[:HAS_EVENT]->(event:StatusEvent)
        WITH mc, count(event) AS event_count
        RETURN mc.token_id AS token_id,
               mc.model_name AS model_name,
               mc.current_status AS status,
               mc.created_at AS created_at,
               mc.version AS version,
               mc.developer_organization AS organization,
               mc.blockchain_address AS creator,
               event_count
        ORDER BY mc.token_id DESC
        """
        results = await neo4j_conn.query(query)
        serialized = serialize_neo4j_data(results)

        output = io.StringIO()
        if serialized:
            writer = csv.DictWriter(output, fieldnames=serialized[0].keys())
            writer.writeheader()
            writer.writerows(serialized)

        from fastapi.responses import StreamingResponse

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=model_cards.csv"}
        )
    except Exception as e:
        logger.exception(f"Error exporting model cards: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export model cards")

@router.get("/explorer/accounts/csv")
async def export_accounts_csv(admin: str = Depends(verify_admin_token)):
    """Export all SMART accounts as CSV (CustomAccount and SMARTAccount labels)."""
    try:
        import csv
        import io

        query = """
        MATCH (u:User)-[rel:HAS_CUSTOM_ACCOUNT|HAS_SMART_ACCOUNT]->(ca)-[:HAS_ROLE]->(r:Role)
        WHERE ca:CustomAccount OR ca:SMARTAccount
        RETURN u.uuid AS user_uuid,
               u.eoa_address AS eoa_address,
               COALESCE(u.smart_id, u.luceid) AS smart_id,
               ca.address AS account_address,
               r.name AS role,
               ca.created_at AS created_at
        ORDER BY ca.created_at DESC
        """
        results = await neo4j_conn.query(query)
        serialized = serialize_neo4j_data(results)

        output = io.StringIO()
        if serialized:
            writer = csv.DictWriter(output, fieldnames=serialized[0].keys())
            writer.writeheader()
            writer.writerows(serialized)

        from fastapi.responses import StreamingResponse

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=accounts.csv"}
        )
    except Exception as e:
        logger.exception(f"Error exporting accounts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export accounts")

@router.get("/explorer/transactions/csv")
async def export_transactions_csv(admin: str = Depends(verify_admin_token)):
    """Export all transactions as CSV."""
    try:
        import csv
        import io

        query = """
        MATCH (mc:ModelCard)-[:HAS_EVENT]->(e:StatusEvent)
        RETURN mc.token_id AS token_id,
               mc.model_name AS model_name,
               e.event_type AS event_type,
               e.timestamp AS timestamp,
               e.tx_hash AS tx_hash,
               e.actor AS actor,
               e.new_status AS new_status,
               e.previous_status AS previous_status
        ORDER BY e.timestamp DESC
        """
        results = await neo4j_conn.query(query)
        serialized = serialize_neo4j_data(results)

        output = io.StringIO()
        if serialized:
            writer = csv.DictWriter(output, fieldnames=serialized[0].keys())
            writer.writeheader()
            writer.writerows(serialized)

        from fastapi.responses import StreamingResponse

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=transactions.csv"}
        )
    except Exception as e:
        logger.exception(f"Error exporting transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export transactions")
