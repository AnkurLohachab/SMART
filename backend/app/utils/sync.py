"""Sync utilities for user verification and model card status between Neo4j and blockchain."""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.utils.smart_chain import smart_chain_manager
from app.db import neo4j_conn
from fastapi import HTTPException

logger = logging.getLogger("smart_sync")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)


STATUS_ENUM_MAP = {
    0: "Created",
    1: "InEvaluation",
    2: "Validated",
    3: "Rejected",
    4: "RevisionRequested",
    5: "Revised",
    6: "Published",
    7: "Deprecated"
}


async def sync_user_verification(uuid: str, eoa_address: str, username: str) -> bool:
    """Sync the user's verification status between Neo4j and the blockchain."""
    try:
        is_registered = await smart_chain_manager.check_if_registered(eoa_address)

        if is_registered:
            await neo4j_conn.set_verified(uuid)
            logger.info(f"User '{uuid}' marked as verified in Neo4j based on blockchain state.")
            return True
        else:
            logger.info(f"User '{uuid}' is not registered on the blockchain. Proceeding with account creation.")

            user_data = await neo4j_conn.get_user_by_uuid(uuid)
            if not user_data:
                logger.error(f"User data not found in Neo4j for UUID '{uuid}'.")
                raise HTTPException(status_code=400, detail="User data not found.")

            creation_result = await smart_chain_manager.create_account_with_username_gasless(eoa_address, username)
            if not creation_result:
                logger.error(f"Failed to create accounts on the blockchain for UUID '{uuid}'.")
                return False

            logger.info(f"Accounts created on the blockchain for UUID '{uuid}': {creation_result}")

            await neo4j_conn.set_verified(uuid)
            logger.info(f"User '{uuid}' marked as verified in Neo4j after account creation.")
            return True

    except HTTPException as he:
        logger.error(f"HTTPException during synchronization: {he.detail}")
        raise he
    except Exception as e:
        logger.exception(f"Error synchronizing user verification for UUID '{uuid}': {str(e)}")
        return False



async def get_neo4j_model_card_status(token_id: int) -> Optional[str]:
    """Get current status from Neo4j for a model card."""
    query = """
    MATCH (mc:ModelCard {token_id: $token_id})
    RETURN mc.current_status as status
    """
    result = await neo4j_conn.query(query, {"token_id": token_id})
    if result and result[0].get("status"):
        return result[0].get("status")
    return None


async def verify_and_sync_model_card_status(token_id: int) -> Dict[str, Any]:
    """Sync Neo4j status to the blockchain status (source of truth) if they differ."""
    from app.utils.blockchain import get_model_card_from_chain

    try:
        chain_data = await get_model_card_from_chain(token_id)
        chain_status = chain_data.get("status")

        if isinstance(chain_status, int):
            chain_status = STATUS_ENUM_MAP.get(chain_status, str(chain_status))

        neo4j_status = await get_neo4j_model_card_status(token_id)

        if neo4j_status is None:
            return {
                "synced": False,
                "chain_status": chain_status,
                "neo4j_status": None,
                "message": f"Model card {token_id} not found in Neo4j",
                "error": True
            }

        if chain_status != neo4j_status:
            sync_query = """
            MATCH (mc:ModelCard {token_id: $token_id})
            SET mc.current_status = $status,
                mc.last_updated = datetime(),
                mc.last_sync = datetime()

            CREATE (event:StatusEvent {
                token_id: $token_id,
                status: $status,
                action: 'StatusSync',
                timestamp: datetime(),
                actor: 'SYSTEM_SYNC',
                event_metadata: $metadata
            })

            WITH mc, event
            CREATE (mc)-[:HAS_EVENT]->(event)

            RETURN mc.current_status as new_status
            """

            metadata = json.dumps({
                "previous_neo4j_status": neo4j_status,
                "chain_status": chain_status,
                "sync_reason": "Blockchain-Neo4j status mismatch",
                "sync_timestamp": datetime.utcnow().isoformat()
            })

            await neo4j_conn.execute(sync_query, {
                "token_id": token_id,
                "status": chain_status,
                "metadata": metadata
            })

            logger.info(f"Synced model card {token_id}: {neo4j_status} -> {chain_status}")

            return {
                "synced": True,
                "token_id": token_id,
                "chain_status": chain_status,
                "neo4j_status": neo4j_status,
                "new_status": chain_status,
                "message": f"Status synced from '{neo4j_status}' to '{chain_status}'"
            }

        return {
            "synced": False,
            "token_id": token_id,
            "chain_status": chain_status,
            "neo4j_status": neo4j_status,
            "message": "Status already in sync"
        }

    except Exception as e:
        logger.error(f"Error syncing model card {token_id}: {str(e)}")
        return {
            "synced": False,
            "token_id": token_id,
            "error": True,
            "message": f"Sync failed: {str(e)}"
        }


async def sync_all_model_cards() -> Dict[str, Any]:
    """Sync all model cards from blockchain to Neo4j and return a summary."""
    query = "MATCH (mc:ModelCard) RETURN mc.token_id as token_id ORDER BY mc.token_id"
    results = await neo4j_conn.query(query, {})

    synced = []
    errors = []
    already_synced = []

    for r in results:
        token_id = r.get("token_id")
        if token_id is None:
            continue

        try:
            result = await verify_and_sync_model_card_status(token_id)

            if result.get("error"):
                errors.append({"token_id": token_id, **result})
            elif result.get("synced"):
                synced.append({"token_id": token_id, **result})
            else:
                already_synced.append({"token_id": token_id, "status": result.get("chain_status")})

        except Exception as e:
            errors.append({"token_id": token_id, "error": str(e)})

    return {
        "total_checked": len(results),
        "synced_count": len(synced),
        "already_synced_count": len(already_synced),
        "error_count": len(errors),
        "synced_details": synced,
        "errors": errors if errors else None
    }


async def get_sync_status_report() -> Dict[str, Any]:
    """Report sync status across all model cards without performing any sync."""
    from app.utils.blockchain import get_model_card_from_chain

    query = "MATCH (mc:ModelCard) RETURN mc.token_id as token_id, mc.current_status as neo4j_status ORDER BY mc.token_id"
    results = await neo4j_conn.query(query, {})

    in_sync = []
    out_of_sync = []
    check_failed = []

    for r in results:
        token_id = r.get("token_id")
        neo4j_status = r.get("neo4j_status")

        try:
            chain_data = await get_model_card_from_chain(token_id)
            chain_status = chain_data.get("status")

            if isinstance(chain_status, int):
                chain_status = STATUS_ENUM_MAP.get(chain_status, str(chain_status))

            if chain_status == neo4j_status:
                in_sync.append({"token_id": token_id, "status": chain_status})
            else:
                out_of_sync.append({
                    "token_id": token_id,
                    "chain_status": chain_status,
                    "neo4j_status": neo4j_status
                })

        except Exception as e:
            check_failed.append({"token_id": token_id, "error": str(e)})

    return {
        "total": len(results),
        "in_sync": len(in_sync),
        "out_of_sync": len(out_of_sync),
        "check_failed": len(check_failed),
        "discrepancies": out_of_sync if out_of_sync else None,
        "failures": check_failed if check_failed else None
    }