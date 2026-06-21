"""Model card lifecycle routes (creation through deprecation)."""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Header
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import logging
from jsonschema import validate, ValidationError

from app.db import neo4j_conn
from app.utils.minio_utils import (
    upload_to_minio,
    get_from_minio,
    upload_to_minio_with_hash,
    compute_content_hash,
    register_storage_mapping
)
from app.utils.blockchain import (
    create_model_card_on_chain,
    submit_for_evaluation,
    validate_model_card,
    reject_model_card,
    request_revision,
    revise_model_card,
    publish_model_card,
    deprecate_model_card,
    get_model_card_from_chain,
    verify_content_integrity,
    get_content_hash_from_chain,
    compute_content_hash
)
from app.utils.neo4j_tracking import (
    track_model_card_in_neo4j,
    update_model_card_status,
    get_model_card_history,
    get_all_model_cards,
    create_or_update_model_lineage,
    create_supersession_relationship,
    get_model_lineage,
    get_version_chain,
    find_deprecated_predecessor,
    find_latest_version
)
from app.utils.smart_model_card_schema import get_model_card_json_schema
from app.utils.identity_binding import (
    get_governance,
    get_actions_for_token,
    get_claim_status,
    list_disputed_actions,
    list_actions_for_actor,
    challenge_action,
    resolve_dispute,
    issue_claim,
    REPUDIATION_REASONS,
    ROLE_TO_CLAIM_TYPES,
    CLAIM_TYPE_NAMES,
)
from app.models_smart_card import ModelCardCreate, ModelCardResponse
from app.routes.admin import verify_admin_token
from app.utils.conflict_of_interest import assert_no_conflict_of_interest
import uuid as _uuid

logger = logging.getLogger(__name__)
router = APIRouter()

class ModelCardSubmit(BaseModel):
    token_id: int
    initiator_address: str

class ModelCardValidate(BaseModel):
    token_id: int
    validator_address: str
    validation_notes: Optional[str] = None

class ModelCardReject(BaseModel):
    token_id: int
    rejector_address: str
    reason: str

class ModelCardRevisionRequest(BaseModel):
    token_id: int
    requester_address: str
    feedback: str

class ModelCardRevise(BaseModel):
    token_id: int
    revisor_address: str
    updated_metadata: dict
    revision_notes: str

class ModelCardSubmitRevision(BaseModel):
    """Simplified revision submission - fetches existing metadata and applies notes"""
    token_id: int
    submitter_address: str
    revision_notes: str
    updated_metadata: Optional[dict] = None

class ModelCardPublish(BaseModel):
    token_id: int
    publisher_address: str

class ModelCardDeprecate(BaseModel):
    token_id: int
    deprecator_address: str
    reason: str


@router.post("/model-cards/create", response_model=ModelCardResponse)
async def create_model_card(model_card: ModelCardCreate):
    """Create a model card: validate, check uniqueness, store in MinIO, mint on-chain, track in Neo4j."""
    try:
        logger.info(f"Creating model card for {model_card.developer_address}")

        schema = get_model_card_json_schema()
        try:
            validate(instance=model_card.metadata, schema=schema)
        except ValidationError as ve:
            logger.error(f"Schema validation failed: {ve.message}")
            raise HTTPException(status_code=400, detail=f"Invalid model card schema: {ve.message}")

        model_details = model_card.metadata.get("1. Model Details", {})
        model_name = model_details.get("Model Name")
        version = model_details.get("Version", "1.0.0")
        developer_org = model_details.get("Developer / Organization")

        if not model_name:
            raise HTTPException(status_code=400, detail="Model Name is required in '1. Model Details'")
        if not developer_org:
            raise HTTPException(status_code=400, detail="Developer / Organization is required in '1. Model Details'")

        uniqueness_query = """
        MATCH (mc:ModelCard)
        WHERE mc.model_name = $model_name
          AND mc.developer_organization = $developer_org
          AND mc.version = $version
        RETURN mc.token_id as existing_token_id
        LIMIT 1
        """
        existing = await neo4j_conn.query(uniqueness_query, {
            "model_name": model_name,
            "developer_org": developer_org,
            "version": version
        })

        if existing and existing[0].get("existing_token_id"):
            existing_id = existing[0].get("existing_token_id")
            raise HTTPException(
                status_code=409,
                detail=f"A model card with name '{model_name}' version '{version}' already exists for organization '{developer_org}' (Token ID: {existing_id}). Use the versioning endpoint to create a new version."
            )

        if "created_at" not in model_card.metadata:
            model_card.metadata["created_at"] = datetime.utcnow().isoformat()

        metadata_json = json.dumps(model_card.metadata, indent=2)
        model_name = model_card.metadata.get("1. Model Details", {}).get("Model Name", "unknown")
        version = model_card.metadata.get("1. Model Details", {}).get("Version", "1.0")
        file_key = f"model-cards/{model_name}_{version}_{datetime.utcnow().timestamp()}.json"

        internal_url, content_hash, privacy_reference = await upload_to_minio_with_hash(
            file_key,
            metadata_json.encode('utf-8'),
            content_type="application/json"
        )

        register_storage_mapping(privacy_reference, internal_url)

        metadata_uri = privacy_reference

        logger.info(f"Metadata uploaded with content hash: {content_hash}")
        logger.info(f"Privacy reference for blockchain: {privacy_reference}")

        tx_result = await create_model_card_on_chain(
            creator=model_card.developer_address,
            metadata_uri=metadata_uri,
            metadata_json=metadata_json
        )

        token_id = tx_result["token_id"]
        logger.info(f"NFT minted with token ID: {token_id}")

        await track_model_card_in_neo4j(
            token_id=token_id,
            status="Created",
            metadata=model_card.metadata,
            address=model_card.developer_address,
            action="NFTMinted",
            additional_data={
                "tx_hash": tx_result.get("tx_hash"),
                "internal_storage_url": internal_url,
                "content_hash": content_hash,
                "privacy_reference": privacy_reference
            },
            creator_uuid=model_card.creator_uuid
        )

        await create_or_update_model_lineage(
            organization=developer_org,
            model_name=model_name,
            token_id=token_id
        )

        return ModelCardResponse(
            success=True,
            token_id=token_id,
            metadata_uri=metadata_uri,
            status="Created",
            tx_hash=tx_result.get("tx_hash"),
            message="Model card created successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create model card: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model-cards/submit")
async def submit_model_card_for_evaluation(submission: ModelCardSubmit):
    """Submit a model card for evaluation (Created/Revised -> InEvaluation)."""
    try:
        logger.info(f"Submitting model card {submission.token_id} for evaluation")

        tx_result = await submit_for_evaluation(
            token_id=submission.token_id,
            initiator=submission.initiator_address
        )

        await update_model_card_status(
            token_id=submission.token_id,
            status="InEvaluation",
            address=submission.initiator_address,
            action="NFTSubmitted",
            event_metadata={"submitted_by": submission.initiator_address}
        )

        return {
            "success": True,
            "token_id": submission.token_id,
            "status": "InEvaluation",
            "transaction_hash": tx_result.get("tx_hash"),
        }

    except Exception as e:
        logger.error(f"Failed to submit model card: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/model-cards/{token_id}/can-act")
async def can_act_on_card(token_id: int, actor: str):
    """Return which lifecycle actions actor can take on this card under separation-of-duties."""
    actor_uuid = await neo4j_conn.get_uuid_for_address(actor)
    actors = await neo4j_conn.get_card_actors(token_id)
    creator_uuid = actors.get("creator_uuid")

    is_creator = bool(actor_uuid and creator_uuid and actor_uuid == creator_uuid)

    is_prior_validator = False
    for ev in actors.get("events") or []:
        if ev.get("action") == "NFTValidated" and ev.get("actor"):
            ev_uuid = await neo4j_conn.get_uuid_for_address(ev["actor"])
            if ev_uuid and ev_uuid == actor_uuid:
                is_prior_validator = True
                break

    return {
        "actor_uuid": actor_uuid,
        "is_creator": is_creator,
        "is_prior_validator": is_prior_validator,
        "can": {
            "validate": not is_creator,
            "reject": not is_creator,
            "request_revision": not is_creator,
            "publish": (not is_creator) and (not is_prior_validator),
            "deprecate": True,
        },
        "reason_if_blocked": (
            "You created this model card; another reviewer must act on it."
            if is_creator
            else (
                "You validated this card; a different publisher must publish it."
                if is_prior_validator
                else None
            )
        ),
    }


@router.post("/model-cards/validate")
async def validate_model_card_endpoint(validation: ModelCardValidate):
    """Validate a model card (InEvaluation -> Validated)."""
    try:
        logger.info(f"Validating model card {validation.token_id}")
        await assert_no_conflict_of_interest(
            token_id=validation.token_id,
            actor_address=validation.validator_address,
            action="validate",
        )

        tx_result = await validate_model_card(
            token_id=validation.token_id,
            validator=validation.validator_address
        )

        await update_model_card_status(
            token_id=validation.token_id,
            status="Validated",
            address=validation.validator_address,
            action="NFTValidated",
            event_metadata={"notes": validation.validation_notes or ""}
        )

        return {
            "success": True,
            "token_id": validation.token_id,
            "status": "Validated",
            "transaction_hash": tx_result.get("tx_hash")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate model card: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model-cards/reject")
async def reject_model_card_endpoint(rejection: ModelCardReject):
    """Reject a model card (InEvaluation -> Rejected, terminal)."""
    try:
        logger.info(f"Rejecting model card {rejection.token_id}")
        await assert_no_conflict_of_interest(
            token_id=rejection.token_id,
            actor_address=rejection.rejector_address,
            action="reject",
        )

        tx_result = await reject_model_card(
            token_id=rejection.token_id,
            rejector=rejection.rejector_address,
            reason=rejection.reason
        )

        await update_model_card_status(
            token_id=rejection.token_id,
            status="Rejected",
            address=rejection.rejector_address,
            action="NFTRejected",
            event_metadata={"reason": rejection.reason}
        )

        return {
            "success": True,
            "token_id": rejection.token_id,
            "status": "Rejected",
            "reason": rejection.reason,
            "transaction_hash": tx_result.get("tx_hash")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reject model card: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model-cards/request-revision")
async def request_model_card_revision(revision_request: ModelCardRevisionRequest):
    """Request revision for a model card (InEvaluation -> RevisionRequested)."""
    try:
        logger.info(f"Requesting revision for model card {revision_request.token_id}")
        await assert_no_conflict_of_interest(
            token_id=revision_request.token_id,
            actor_address=revision_request.requester_address,
            action="request_revision",
        )

        tx_result = await request_revision(
            token_id=revision_request.token_id,
            requester=revision_request.requester_address,
            feedback=revision_request.feedback
        )

        await update_model_card_status(
            token_id=revision_request.token_id,
            status="RevisionRequested",
            address=revision_request.requester_address,
            action="RevisionRequested",
            event_metadata={"feedback": revision_request.feedback}
        )

        return {
            "success": True,
            "token_id": revision_request.token_id,
            "status": "RevisionRequested",
            "feedback": revision_request.feedback,
            "transaction_hash": tx_result.get("tx_hash")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to request revision: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model-cards/revise")
async def revise_model_card_endpoint(revision: ModelCardRevise):
    """Revise a model card as a PATCH version within the same NFT (RevisionRequested -> Revised)."""
    try:
        logger.info(f"Revising model card {revision.token_id}")

        query = """
        MATCH (mc:ModelCard {token_id: $token_id})
        RETURN mc.version as current_version, mc.model_name as model_name
        """
        result = await neo4j_conn.query(query, {"token_id": revision.token_id})

        current_version = result[0].get("current_version", "1.0.0") if result else "1.0.0"
        model_name = result[0].get("model_name", "unknown") if result else "unknown"

        version_parts = current_version.split(".")
        version_parts[-1] = str(int(version_parts[-1]) + 1)
        new_version = ".".join(version_parts)

        revision.updated_metadata["version"] = new_version
        revision.updated_metadata["previous_version"] = current_version
        revision.updated_metadata["revised_at"] = datetime.utcnow().isoformat()

        metadata_json = json.dumps(revision.updated_metadata, indent=2)
        file_key = f"model-cards/{model_name}_v{new_version}_{datetime.utcnow().timestamp()}.json"

        new_metadata_uri = await upload_to_minio(
            file_key,
            metadata_json.encode('utf-8'),
            content_type="application/json"
        )

        tx_result = await revise_model_card(
            token_id=revision.token_id,
            revisor=revision.revisor_address,
            new_metadata_uri=new_metadata_uri,
            revision_notes=revision.revision_notes,
            metadata_json=metadata_json
        )

        await track_model_card_in_neo4j(
            token_id=revision.token_id,
            status="Revised",
            metadata=revision.updated_metadata,
            address=revision.revisor_address,
            action="NFTRevised",
            additional_data={
                "revision_notes": revision.revision_notes,
                "new_metadata_uri": new_metadata_uri,
                "version": new_version,
                "previous_version": current_version,
            },
        )

        update_query = """
        MATCH (mc:ModelCard {token_id: $token_id})
        SET mc.version = $new_version,
            mc.previous_version = $current_version,
            mc.updated_at = datetime()
        """
        await neo4j_conn.execute(update_query, {
            "token_id": revision.token_id,
            "new_version": new_version,
            "current_version": current_version
        })

        resubmit_tx = None
        try:
            resubmit_result = await submit_for_evaluation(
                token_id=revision.token_id,
                initiator=revision.revisor_address,
            )
            resubmit_tx = resubmit_result.get("tx_hash")
            await update_model_card_status(
                token_id=revision.token_id,
                status="InEvaluation",
                address=revision.revisor_address,
                action="NFTSubmitted",
                event_metadata={"after_revision": True},
            )
        except Exception as exc:
            logger.warning(
                "auto-resubmit after revise failed for token %s: %s",
                revision.token_id, exc,
            )

        return {
            "success": True,
            "token_id": revision.token_id,
            "status": "InEvaluation" if resubmit_tx else "Revised",
            "version": new_version,
            "previous_version": current_version,
            "new_metadata_uri": new_metadata_uri,
            "transaction_hash": tx_result.get("tx_hash"),
            "resubmit_tx": resubmit_tx,
        }

    except Exception as e:
        logger.error(f"Failed to revise model card: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model-cards/submit-revision")
async def submit_revision_endpoint(revision: ModelCardSubmitRevision):
    """Simplified revision submission: create a PATCH version (RevisionRequested -> Revised)."""
    try:
        logger.info(f"Submit revision for model card {revision.token_id}")

        query = """
        MATCH (mc:ModelCard {token_id: $token_id})
        RETURN mc.current_status as status,
               mc.version as version,
               mc.model_name as model_name,
               mc.metadata_uri as metadata_uri
        """
        result = await neo4j_conn.query(query, {"token_id": revision.token_id})

        if not result:
            raise HTTPException(status_code=404, detail="Model card not found")

        current_status = result[0].get("status")
        if current_status != "RevisionRequested":
            raise HTTPException(
                status_code=400,
                detail=f"Model card must be in RevisionRequested status to revise. Current status: {current_status}"
            )

        if revision.updated_metadata:
            updated_metadata = revision.updated_metadata
        else:
            card_query = """
            MATCH (mc:ModelCard {token_id: $token_id})
            RETURN mc {.*} as card_data
            """
            card_result = await neo4j_conn.query(card_query, {"token_id": revision.token_id})

            if card_result:
                card_data = card_result[0].get("card_data", {})
                updated_metadata = {
                    "1. Model Details": {
                        "Model Name": card_data.get("model_name"),
                        "Version": card_data.get("version"),
                        "Organization": card_data.get("developer_organization"),
                        "Description": card_data.get("description"),
                        "Intended Purpose": card_data.get("intended_purpose"),
                        "Algorithm(s) Used": card_data.get("algorithms_used"),
                    },
                    "revision_info": {
                        "revision_notes": revision.revision_notes,
                        "revised_by": revision.submitter_address,
                        "revised_at": datetime.utcnow().isoformat()
                    }
                }
            else:
                updated_metadata = {
                    "revision_info": {
                        "revision_notes": revision.revision_notes,
                        "revised_by": revision.submitter_address,
                        "revised_at": datetime.utcnow().isoformat()
                    }
                }

        updated_metadata["revision_info"] = {
            "revision_notes": revision.revision_notes,
            "revised_by": revision.submitter_address,
            "revised_at": datetime.utcnow().isoformat()
        }

        full_revision = ModelCardRevise(
            token_id=revision.token_id,
            revisor_address=revision.submitter_address,
            updated_metadata=updated_metadata,
            revision_notes=revision.revision_notes
        )

        return await revise_model_card_endpoint(full_revision)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit revision: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model-cards/publish")
async def publish_model_card_endpoint(publication: ModelCardPublish):
    """Publish a validated model card (Validated -> Published)."""
    try:
        logger.info(f"Publishing model card {publication.token_id}")
        await assert_no_conflict_of_interest(
            token_id=publication.token_id,
            actor_address=publication.publisher_address,
            action="publish",
        )

        tx_result = await publish_model_card(
            token_id=publication.token_id,
            publisher=publication.publisher_address
        )

        await update_model_card_status(
            token_id=publication.token_id,
            status="Published",
            address=publication.publisher_address,
            action="NFTPublished",
            event_metadata={"publisher": publication.publisher_address}
        )

        return {
            "success": True,
            "token_id": publication.token_id,
            "status": "Published",
            "transaction_hash": tx_result.get("tx_hash")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to publish model card: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model-cards/deprecate")
async def deprecate_model_card_endpoint(deprecation: ModelCardDeprecate):
    """Deprecate a published model card (Published -> Deprecated, terminal)."""
    try:
        logger.info(f"Deprecating model card {deprecation.token_id}")

        tx_result = await deprecate_model_card(
            token_id=deprecation.token_id,
            deprecator=deprecation.deprecator_address,
            reason=deprecation.reason
        )

        await update_model_card_status(
            token_id=deprecation.token_id,
            status="Deprecated",
            address=deprecation.deprecator_address,
            action="NFTDeprecated",
            event_metadata={"reason": deprecation.reason}
        )

        return {
            "success": True,
            "token_id": deprecation.token_id,
            "status": "Deprecated",
            "reason": deprecation.reason,
            "transaction_hash": tx_result.get("tx_hash")
        }

    except Exception as e:
        logger.error(f"Failed to deprecate model card: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/model-cards/sync-report")
async def get_sync_report():
    """Report sync status across all model cards without performing sync."""
    from app.utils.sync import get_sync_status_report

    try:
        result = await get_sync_status_report()
        return result

    except Exception as e:
        logger.error(f"Failed to get sync report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model-cards/sync-all")
async def sync_all_model_cards_endpoint():
    """Sync all model cards from blockchain to Neo4j (admin operation)."""
    from app.utils.sync import sync_all_model_cards

    try:
        result = await sync_all_model_cards()
        return result

    except Exception as e:
        logger.error(f"Failed to sync all model cards: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class SupersessionRequest(BaseModel):
    deprecated_token_id: int
    successor_token_id: int
    reason: Optional[str] = None


@router.post("/model-cards/mark-superseded")
async def mark_model_card_superseded(request: SupersessionRequest):
    """Mark a deprecated model card as superseded by a new version."""
    try:
        deprecated_query = """
        MATCH (mc:ModelCard {token_id: $token_id})
        RETURN mc.current_status as status
        """
        deprecated_result = await neo4j_conn.query(deprecated_query, {"token_id": request.deprecated_token_id})

        if not deprecated_result:
            raise HTTPException(status_code=404, detail=f"Model card {request.deprecated_token_id} not found")

        if deprecated_result[0].get("status") != "Deprecated":
            raise HTTPException(
                status_code=400,
                detail=f"Model card {request.deprecated_token_id} is not deprecated (status: {deprecated_result[0].get('status')})"
            )

        result = await create_supersession_relationship(
            deprecated_token_id=request.deprecated_token_id,
            successor_token_id=request.successor_token_id,
            reason=request.reason
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark superseded: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-cards/{token_id}/revision-history")
async def get_revision_history(token_id: int):
    """Return the revision dialogue: each RequestRevision paired with the next Revise."""
    query = """
    MATCH (mc:ModelCard {token_id: $token_id})-[:HAS_EVENT]->(e:StatusEvent)
    WHERE e.action IN ['RevisionRequested', 'NFTRevised']
    RETURN e.action AS action,
           e.actor AS actor,
           e.timestamp AS timestamp,
           e.event_metadata AS event_metadata
    ORDER BY e.timestamp ASC
    """
    rows = await neo4j_conn.query(query, {"token_id": int(token_id)})

    cycles: List[Dict[str, Any]] = []
    pending_request = None
    cycle_index = 0
    for r in rows:
        action = r.get("action")
        meta_raw = r.get("event_metadata") or "{}"
        try:
            meta = json.loads(meta_raw) if isinstance(meta_raw, str) else (meta_raw or {})
        except Exception:
            meta = {}
        if action == "RevisionRequested":
            cycle_index += 1
            pending_request = {
                "cycle": cycle_index,
                "request": {
                    "by": r.get("actor"),
                    "feedback": meta.get("feedback") or meta.get("reason") or "",
                    "at": r.get("timestamp"),
                },
                "response": None,
            }
            cycles.append(pending_request)
        elif action == "NFTRevised":
            response = {
                "by": r.get("actor"),
                "notes": meta.get("revision_notes") or meta.get("notes") or "",
                "at": r.get("timestamp"),
            }
            if pending_request and pending_request["response"] is None:
                pending_request["response"] = response
                pending_request = None
            else:
                cycles.append({"cycle": None, "request": None, "response": response})

    revision_count = sum(1 for c in cycles if c.get("response"))
    open_requests = sum(1 for c in cycles if c.get("request") and not c.get("response"))

    return {
        "token_id": int(token_id),
        "revision_count": revision_count,
        "open_requests": open_requests,
        "cycles": cycles,
    }


@router.get("/model-cards/{token_id}")
async def get_model_card(
    token_id: int,
    actor: Optional[str] = None,
    x_admin_token: Optional[str] = Header(None),
):
    """Get detailed information about a model card. Pre-publication cards are restricted to creator/actors/admin."""
    try:
        query = """
        MATCH (mc:ModelCard {token_id: $token_id})
        OPTIONAL MATCH (mc)-[:HAS_EVENT]->(event:StatusEvent)
        RETURN mc, collect(event) as events
        """
        result = await neo4j_conn.query(query, {"token_id": token_id})

        if not result or not result[0].get("mc"):
            raise HTTPException(status_code=404, detail="Model card not found")

        neo4j_data = result[0].get("mc", {})
        events = result[0].get("events", [])

        PUBLIC_STATUSES = {"Published", "Deprecated"}
        current_status = neo4j_data.get("current_status")
        if current_status not in PUBLIC_STATUSES:
            allowed = False
            if x_admin_token:
                try:
                    from app.routes.admin import _verify_jwt_token
                    if _verify_jwt_token(x_admin_token):
                        allowed = True
                except Exception:
                    pass
            if (not allowed) and actor:
                actor_uuid = await neo4j_conn.get_uuid_for_address(actor)
                if actor_uuid:
                    actors_record = await neo4j_conn.get_card_actors(token_id)
                    if actors_record.get("creator_uuid") == actor_uuid:
                        allowed = True
                    else:
                        for ev in actors_record.get("events") or []:
                            ev_actor = ev.get("actor")
                            if ev_actor and (await neo4j_conn.get_uuid_for_address(ev_actor)) == actor_uuid:
                                allowed = True
                                break
                    if not allowed:
                        try:
                            roles = await neo4j_conn.get_user_roles(actor_uuid)
                        except Exception:
                            roles = []
                        privileged = {"Reviewer", "Authenticator", "Publisher", "Admin"}
                        if any(r in privileged for r in (roles or [])):
                            allowed = True
            if not allowed:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "This model card has not been published yet. "
                        "Only the author and reviewers can view it."
                    ),
                )

        on_chain_data = None
        blockchain_synced = False
        try:
            on_chain_data = await get_model_card_from_chain(token_id)
            blockchain_synced = True
        except Exception as blockchain_error:
            logger.warning(f"Could not fetch blockchain data for token {token_id}: {blockchain_error}")
            on_chain_data = {
                "status": neo4j_data.get("current_status", "Unknown"),
                "creator": neo4j_data.get("blockchain_address", "Unknown"),
                "metadata_uri": neo4j_data.get("metadata_uri", ""),
                "blockchain_synced": False
            }

        metadata = None
        if neo4j_data.get("full_metadata"):
            try:
                metadata = json.loads(neo4j_data.get("full_metadata"))
            except:
                metadata = neo4j_data.get("full_metadata")

        governance: Optional[Dict[str, Any]] = None
        try:
            governance = get_governance(token_id)
        except Exception as gov_err:
            logger.debug(f"governance lookup failed for token {token_id}: {gov_err}")
            governance = {"state": "unknown", "actions": [], "reason": None}

        return {
            "token_id": token_id,
            "on_chain": on_chain_data,
            "history": events,
            "current_status": neo4j_data.get("current_status", on_chain_data.get("status")),
            "blockchain_synced": blockchain_synced,
            "metadata": metadata,
            "model_name": neo4j_data.get("model_name"),
            "version": neo4j_data.get("version"),
            "description": neo4j_data.get("description"),
            "developer_organization": neo4j_data.get("developer_organization"),
            "created_at": neo4j_data.get("created_at"),
            "governance": governance,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model card: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-cards")
async def list_model_cards(
    status: Optional[str] = None,
    organization: Optional[str] = None,
    model_name: Optional[str] = None,
    include: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    x_admin_token: Optional[str] = Header(None),
):
    """List model cards. Returns only Published/Deprecated unless include=all (admin)."""
    try:
        PUBLIC_STATUSES = {"Published", "Deprecated"}
        bypass_public_filter = False
        if include == "all":
            try:
                if x_admin_token:
                    from app.routes.admin import _verify_jwt_token
                    if _verify_jwt_token(x_admin_token):
                        bypass_public_filter = True
                    else:
                        raise HTTPException(status_code=401, detail="Invalid admin token for include=all")
                else:
                    raise HTTPException(status_code=401, detail="include=all requires an admin token")
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=401, detail="Invalid admin token for include=all")

        if status:
            if (not bypass_public_filter) and status not in PUBLIC_STATUSES:
                return {"model_cards": [], "total": 0, "skip": skip, "limit": limit}

        query = "MATCH (mc:ModelCard)"
        conditions = []
        params = {"skip": skip, "limit": limit}

        if status:
            conditions.append("mc.current_status = $status")
            params["status"] = status
        elif not bypass_public_filter:
            conditions.append("mc.current_status IN $public_statuses")
            params["public_statuses"] = list(PUBLIC_STATUSES)

        if organization:
            conditions.append("mc.developer_organization = $organization")
            params["organization"] = organization

        if model_name:
            conditions.append("mc.model_name = $model_name")
            params["model_name"] = model_name

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += """
        RETURN mc
        ORDER BY mc.created_at DESC
        SKIP $skip
        LIMIT $limit
        """

        results = await neo4j_conn.query(query, params)

        model_cards = [r.get("mc") for r in results if r.get("mc")]

        if model_cards:
            from app.utils.identity_binding import get_actions_for_token
            for mc in model_cards:
                tid = mc.get("token_id")
                if tid is None:
                    continue
                tally = {"total": 0, "open": 0, "split": 0, "resolved": 0}
                try:
                    for a in get_actions_for_token(int(tid)):
                        st = a.get("identity_status")
                        if st in ("Disputed", "ResolvedValid", "ResolvedInvalid"):
                            tally["total"] += 1
                            if st == "Disputed":
                                tally["open"] += 1
                            else:
                                tally["resolved"] += 1
                except Exception as exc:
                    logger.debug(f"challenge tally failed for token {tid}: {exc}")
                try:
                    split_q = await neo4j_conn.query(
                        "MATCH (dc:DisputeCase {token_id: $tid, outcome: 'Split'}) RETURN count(dc) AS n",
                        {"tid": int(tid)},
                    )
                    split_n = int(split_q[0].get("n", 0)) if split_q else 0
                    if split_n:
                        moved = min(split_n, tally["open"])
                        tally["open"] -= moved
                        tally["split"] += moved
                except Exception:
                    pass
                mc["challenges"] = tally

        return {
            "model_cards": model_cards,
            "count": len(model_cards),
            "filters_applied": {
                "status": status,
                "organization": organization,
                "model_name": model_name
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list model cards: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/organizations")
async def list_organizations():
    """List all organizations that have submitted model cards, with model counts."""
    try:
        query = """
        MATCH (mc:ModelCard)
        WHERE mc.developer_organization IS NOT NULL
        RETURN mc.developer_organization as organization,
               count(mc) as model_count,
               collect(DISTINCT mc.model_name) as model_names
        ORDER BY model_count DESC
        """

        results = await neo4j_conn.query(query, {})

        organizations = []
        for r in results:
            organizations.append({
                "organization": r.get("organization"),
                "model_count": r.get("model_count"),
                "models": r.get("model_names", [])
            })

        return {
            "organizations": organizations,
            "total_organizations": len(organizations)
        }

    except Exception as e:
        logger.error(f"Failed to list organizations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/organizations/{organization}/models")
async def list_organization_models(organization: str):
    """List model cards for an organization, grouped by name with version history."""
    try:
        query = """
        MATCH (mc:ModelCard)
        WHERE mc.developer_organization = $organization
        RETURN mc.model_name as model_name,
               mc.token_id as token_id,
               mc.version as version,
               mc.current_status as status,
               mc.created_at as created_at
        ORDER BY mc.model_name, mc.created_at DESC
        """

        results = await neo4j_conn.query(query, {"organization": organization})

        models = {}
        for r in results:
            name = r.get("model_name")
            if name not in models:
                models[name] = {
                    "model_name": name,
                    "versions": []
                }
            models[name]["versions"].append({
                "token_id": r.get("token_id"),
                "version": r.get("version"),
                "status": r.get("status"),
                "created_at": r.get("created_at")
            })

        return {
            "organization": organization,
            "models": list(models.values()),
            "total_models": len(models)
        }

    except Exception as e:
        logger.error(f"Failed to list organization models: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-cards/{token_id}/versions")
async def get_version_history(token_id: int):
    """Get the complete version history for a model card."""
    try:
        query = """
        MATCH (mc:ModelCard {token_id: $token_id})-[:HAS_EVENT]->(event:StatusEvent)
        WHERE event.action = 'NFTRevised' OR event.action = 'NFTMinted'
        RETURN event
        ORDER BY event.timestamp DESC
        """

        results = await neo4j_conn.query(query, {"token_id": token_id})

        versions = []
        for idx, event in enumerate(results):
            version_info = {
                "version_number": idx + 1,
                "version": event.get("metadata", {}).get("version", "1.0.0"),
                "previous_version": event.get("metadata", {}).get("previous_version"),
                "timestamp": event.get("timestamp"),
                "action": event.get("action"),
                "address": event.get("address"),
                "metadata_uri": event.get("metadata", {}).get("new_metadata_uri") or event.get("metadata", {}).get("metadata_uri"),
                "notes": event.get("metadata", {}).get("revision_notes")
            }
            versions.append(version_info)

        return {
            "token_id": token_id,
            "total_versions": len(versions),
            "versions": versions
        }

    except Exception as e:
        logger.error(f"Failed to get version history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model-cards/create-version")
async def create_new_version(model_card: ModelCardCreate):
    """Create a new MAJOR version (new NFT) of a model card; the latest version must be Deprecated."""
    try:
        logger.info(f"Creating new version for developer {model_card.developer_address}")

        model_details = model_card.metadata.get("1. Model Details", {})
        model_name = model_details.get("Model Name")
        developer_org = model_details.get("Developer / Organization")

        if not model_name:
            raise HTTPException(status_code=400, detail="Model Name is required in '1. Model Details'")
        if not developer_org:
            raise HTTPException(status_code=400, detail="Developer / Organization is required in '1. Model Details'")

        latest_version = await find_latest_version(developer_org, model_name)

        deprecated_predecessor = await find_deprecated_predecessor(developer_org, model_name)

        parent_token_id = None
        current_version = "0.0.0"

        if latest_version:
            current_version = latest_version.get("version", "1.0.0")
            parent_token_id = latest_version.get("token_id")
            parent_status = latest_version.get("status", "")

            if parent_status != "Deprecated":
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot create a new version: The current version (#{parent_token_id}, v{current_version}) "
                           f"must be deprecated first. Current status is '{parent_status}'. "
                           f"Please deprecate the existing model card before creating a new version."
                )

            try:
                version_parts = current_version.split(".")
                if len(version_parts) >= 3:
                    version_parts[0] = str(int(version_parts[0]) + 1)
                    version_parts[1] = "0"
                    version_parts[2] = "0"
                    new_version = ".".join(version_parts[:3])
                else:
                    new_version = f"{int(version_parts[0]) + 1}.0.0"
            except (ValueError, IndexError):
                new_version = "2.0.0"
                logger.warning(f"Could not parse version '{current_version}', defaulting to {new_version}")
        else:
            new_version = "1.0.0"
            logger.info(f"No existing versions found for '{model_name}' by '{developer_org}', starting at {new_version}")

        if "1. Model Details" in model_card.metadata:
            model_card.metadata["1. Model Details"]["Version"] = new_version
        model_card.metadata["version"] = new_version

        if parent_token_id:
            model_card.metadata["parent_token_id"] = parent_token_id
            model_card.metadata["parent_version"] = current_version

        if deprecated_predecessor:
            model_card.metadata["supersedes_deprecated"] = deprecated_predecessor.get("token_id")
            model_card.metadata["deprecation_successor"] = True

        model_card.metadata["created_at"] = datetime.utcnow().isoformat()

        schema = get_model_card_json_schema()
        try:
            validate(instance=model_card.metadata, schema=schema)
        except ValidationError as ve:
            logger.error(f"Schema validation failed: {ve.message}")
            raise HTTPException(status_code=400, detail=f"Invalid model card schema: {ve.message}")

        metadata_json = json.dumps(model_card.metadata, indent=2)
        file_key = f"model-cards/{model_name}_v{new_version}_{datetime.utcnow().timestamp()}.json"

        metadata_uri = await upload_to_minio(
            file_key,
            metadata_json.encode('utf-8'),
            content_type="application/json"
        )

        logger.info(f"Metadata uploaded to MinIO: {metadata_uri}")

        tx_result = await create_model_card_on_chain(
            creator=model_card.developer_address,
            metadata_uri=metadata_uri,
            metadata_json=metadata_json
        )

        token_id = tx_result["token_id"]
        logger.info(f"NFT minted with token ID: {token_id}")

        await track_model_card_in_neo4j(
            token_id=token_id,
            status="Created",
            metadata={
                **model_card.metadata,
                "version": new_version,
                "parent_token_id": parent_token_id
            },
            address=model_card.developer_address,
            action="NFTMinted",
            additional_data={
                "tx_hash": tx_result.get("tx_hash"),
                "version": new_version,
                "is_new_version": True,
                "supersedes_deprecated": deprecated_predecessor.get("token_id") if deprecated_predecessor else None
            }
        )

        await create_or_update_model_lineage(
            organization=developer_org,
            model_name=model_name,
            token_id=token_id
        )

        if parent_token_id:
            relationship_query = """
            MATCH (parent:ModelCard {token_id: $parent_token_id})
            MATCH (child:ModelCard {token_id: $child_token_id})
            MERGE (parent)-[:HAS_VERSION]->(child)
            SET child.parent_token_id = $parent_token_id
            """
            await neo4j_conn.execute(relationship_query, {
                "parent_token_id": parent_token_id,
                "child_token_id": token_id
            })

        supersession_info = None
        if deprecated_predecessor:
            supersession_result = await create_supersession_relationship(
                deprecated_token_id=deprecated_predecessor.get("token_id"),
                successor_token_id=token_id,
                reason=f"New version {new_version} created to replace deprecated v{deprecated_predecessor.get('version')}"
            )
            supersession_info = supersession_result
            logger.info(f"Created supersession: #{token_id} supersedes deprecated #{deprecated_predecessor.get('token_id')}")

        response_message = f"New version {new_version} created successfully"
        if parent_token_id:
            response_message += f" (parent: #{parent_token_id})"
        if supersession_info:
            response_message += f" - supersedes deprecated #{deprecated_predecessor.get('token_id')}"

        return ModelCardResponse(
            success=True,
            token_id=token_id,
            metadata_uri=metadata_uri,
            status="Created",
            tx_hash=tx_result.get("tx_hash"),
            message=response_message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create new version: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-cards/{token_id}/compare/{other_token_id}")
async def compare_versions(token_id: int, other_token_id: int):
    """Compare two versions of a model card and return their differences."""
    try:
        query = """
        MATCH (mc:ModelCard {token_id: $token_id})
        RETURN mc
        """

        card1 = await neo4j_conn.query(query, {"token_id": token_id})
        card2 = await neo4j_conn.query(query, {"token_id": other_token_id})

        if not card1 or not card2:
            raise HTTPException(status_code=404, detail="One or both model cards not found")

        return {
            "token_id_1": token_id,
            "token_id_2": other_token_id,
            "version_1": card1[0].get("version", "unknown"),
            "version_2": card2[0].get("version", "unknown"),
            "card_1": card1[0],
            "card_2": card2[0],
            "comparison_timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compare versions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-cards/{token_id}/verify")
async def verify_model_card_integrity(token_id: int):
    """Verify a model card's integrity by comparing the on-chain hash with the MinIO metadata hash."""
    try:
        on_chain_data = await get_model_card_from_chain(token_id)

        metadata_uri = on_chain_data.get("metadata_uri")
        on_chain_hash = on_chain_data.get("content_hash")

        if not metadata_uri:
            raise HTTPException(status_code=404, detail="Model card metadata URI not found")

        try:
            metadata_content = await get_from_minio(metadata_uri)
            if isinstance(metadata_content, bytes):
                metadata_json = metadata_content.decode('utf-8')
            else:
                metadata_json = metadata_content
        except Exception as e:
            logger.error(f"Failed to fetch metadata from MinIO: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Could not fetch metadata from storage: {str(e)}"
            )

        verification_result = await verify_content_integrity(token_id, metadata_json)

        return {
            "token_id": token_id,
            "is_valid": verification_result["is_valid"],
            "on_chain_hash": verification_result["on_chain_hash"],
            "computed_hash": verification_result["computed_hash"],
            "metadata_uri": metadata_uri,
            "status": on_chain_data.get("status"),
            "verification_timestamp": datetime.utcnow().isoformat(),
            "message": verification_result["message"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to verify model card integrity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model-cards/{token_id}/verify-content")
async def verify_with_provided_content(token_id: int, content: dict):
    """Verify model card integrity using user-provided content against the on-chain hash."""
    try:
        metadata_json = json.dumps(content.get("metadata", content), indent=2, sort_keys=True, default=str)

        verification_result = await verify_content_integrity(token_id, metadata_json)

        return {
            "token_id": token_id,
            "is_valid": verification_result["is_valid"],
            "on_chain_hash": verification_result["on_chain_hash"],
            "computed_hash": verification_result["computed_hash"],
            "verification_timestamp": datetime.utcnow().isoformat(),
            "message": verification_result["message"]
        }

    except Exception as e:
        logger.error(f"Failed to verify content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-cards/{token_id}/blockchain-info")
async def get_blockchain_info(token_id: int):
    """Get blockchain information for a model card."""
    try:
        on_chain_data = await get_model_card_from_chain(token_id)

        return {
            "token_id": token_id,
            "blockchain_data": on_chain_data,
            "integrity": {
                "content_hash": on_chain_data.get("content_hash"),
                "hash_algorithm": "SHA-256",
                "verification_endpoint": f"/api/model-cards/{token_id}/verify",
                "description": "Hash of model card metadata stored immutably on blockchain"
            },
            "storage": {
                "metadata_uri": on_chain_data.get("metadata_uri"),
                "storage_type": "MinIO Object Storage"
            }
        }

    except Exception as e:
        logger.error(f"Failed to get blockchain info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versioning-strategy")
async def get_versioning_strategy():
    """Return documentation about the model card versioning strategy."""
    return {
        "versioning_strategy": {
            "type": "Semantic Versioning (MAJOR.MINOR.PATCH)",
            "namespace": "Organization-scoped (each organization has independent version sequences)",
            "uniqueness": "Unique combination of (Organization, Model Name, Version)"
        },
        "version_types": {
            "PATCH": {
                "example": "1.0.0 -> 1.0.1",
                "endpoint": "POST /api/model-cards/revise",
                "nft_behavior": "SAME NFT token - metadata updated",
                "use_cases": [
                    "Fixes after Authenticator feedback",
                    "Documentation updates",
                    "Minor corrections",
                    "Bug fixes in model documentation"
                ],
                "status_flow": "RevisionRequested -> Revised"
            },
            "MAJOR": {
                "example": "1.0.0 -> 2.0.0",
                "endpoint": "POST /api/model-cards/create-version",
                "nft_behavior": "NEW NFT token created, linked to parent",
                "precondition": "Current latest version MUST be in 'Deprecated' status; otherwise HTTP 400.",
                "use_cases": [
                    "Significant model updates",
                    "Breaking changes",
                    "Major algorithm changes",
                    "New model architecture",
                    "Complete re-training"
                ],
                "status_flow": "Predecessor Deprecated -> new card Created (with SUPERSEDES link)"
            }
        },
        "organization_isolation": {
            "description": "Different organizations can have models with the same name",
            "example": {
                "org_a": {"model": "BioAnalyzer", "versions": ["1.0.0", "2.0.0"]},
                "org_b": {"model": "BioAnalyzer", "versions": ["1.0.0"]},
                "note": "These are completely independent model cards"
            }
        },
        "uniqueness_constraints": {
            "rule": "Within an organization, (model_name + version) must be unique",
            "allowed": [
                "Org A: BioAnalyzer v1.0.0",
                "Org A: BioAnalyzer v2.0.0 (different version)",
                "Org B: BioAnalyzer v1.0.0 (different organization)"
            ],
            "not_allowed": [
                "Org A: BioAnalyzer v1.0.0 (duplicate - already exists)"
            ]
        },
        "api_endpoints": {
            "create_initial": "POST /api/model-cards/create",
            "create_major_version": "POST /api/model-cards/create-version",
            "create_patch_version": "POST /api/model-cards/revise",
            "list_versions": "GET /api/model-cards/{token_id}/versions",
            "list_by_org": "GET /api/organizations/{org}/models",
            "list_all_orgs": "GET /api/organizations"
        }
    }



@router.post("/model-cards/{token_id}/sync")
async def sync_model_card_status(token_id: int):
    """Sync a single model card's status from blockchain (source of truth) to Neo4j."""
    from app.utils.sync import verify_and_sync_model_card_status

    try:
        result = await verify_and_sync_model_card_status(token_id)
        return result

    except Exception as e:
        logger.error(f"Failed to sync model card {token_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/dashboard/authenticator")
async def get_authenticator_dashboard(authenticator_address: Optional[str] = None):
    """Dashboard data for Authenticators: pending cards, prior actions, and stats."""
    try:
        pending_query = """
        MATCH (pending:ModelCard)
        WHERE pending.current_status = 'InEvaluation'
        RETURN pending.token_id as token_id,
               pending.model_name as model_name,
               pending.developer_organization as organization,
               pending.created_at as created_at,
               pending.version as version,
               pending.blockchain_address as creator_address
        ORDER BY pending.created_at ASC
        """
        pending_results = await neo4j_conn.query(pending_query, {})

        my_actions = []
        if authenticator_address:
            actions_query = """
            MATCH (mc:ModelCard)-[:HAS_EVENT]->(event:StatusEvent)
            WHERE event.actor = $address
              AND event.action IN ['NFTValidated', 'NFTRejected', 'RevisionRequested']
            RETURN DISTINCT mc.token_id as token_id,
                   mc.model_name as model_name,
                   mc.current_status as current_status,
                   event.action as last_action,
                   event.timestamp as action_timestamp
            ORDER BY event.timestamp DESC
            LIMIT 20
            """
            actions_results = await neo4j_conn.query(actions_query, {"address": authenticator_address})
            my_actions = actions_results

        stats_query = """
        MATCH (mc:ModelCard)
        RETURN mc.current_status as status, count(*) as count
        """
        stats_results = await neo4j_conn.query(stats_query, {})
        stats_by_status = {r.get("status"): r.get("count") for r in stats_results}

        return {
            "pending_validation": pending_results,
            "my_actions": my_actions,
            "stats": {
                "pending_count": len(pending_results),
                "total_in_evaluation": stats_by_status.get("InEvaluation", 0),
                "total_validated": stats_by_status.get("Validated", 0),
                "total_rejected": stats_by_status.get("Rejected", 0),
                "actions_count": len(my_actions)
            }
        }

    except Exception as e:
        logger.error(f"Failed to get authenticator dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/publisher")
async def get_publisher_dashboard(publisher_address: Optional[str] = None):
    """Dashboard data for Publishers: cards ready to publish, published cards, prior actions, and stats."""
    try:
        ready_query = """
        MATCH (ready:ModelCard)
        WHERE ready.current_status = 'Validated'
        RETURN ready.token_id as token_id,
               ready.model_name as model_name,
               ready.developer_organization as organization,
               ready.version as version,
               ready.created_at as created_at
        ORDER BY ready.created_at ASC
        """
        ready_results = await neo4j_conn.query(ready_query, {})

        published_query = """
        MATCH (published:ModelCard)
        WHERE published.current_status = 'Published'
        RETURN published.token_id as token_id,
               published.model_name as model_name,
               published.developer_organization as organization,
               published.version as version,
               published.created_at as created_at
        ORDER BY published.created_at DESC
        """
        published_results = await neo4j_conn.query(published_query, {})

        my_actions = []
        if publisher_address:
            actions_query = """
            MATCH (mc:ModelCard)-[:HAS_EVENT]->(event:StatusEvent)
            WHERE event.actor = $address
              AND event.action IN ['NFTPublished', 'NFTDeprecated']
            RETURN DISTINCT mc.token_id as token_id,
                   mc.model_name as model_name,
                   mc.current_status as current_status,
                   event.action as last_action,
                   event.timestamp as action_timestamp
            ORDER BY event.timestamp DESC
            LIMIT 20
            """
            actions_results = await neo4j_conn.query(actions_query, {"address": publisher_address})
            my_actions = actions_results

        stats_query = """
        MATCH (mc:ModelCard)
        RETURN mc.current_status as status, count(*) as count
        """
        stats_results = await neo4j_conn.query(stats_query, {})
        stats_by_status = {r.get("status"): r.get("count") for r in stats_results}

        return {
            "ready_to_publish": ready_results,
            "published_cards": published_results,
            "my_actions": my_actions,
            "stats": {
                "ready_count": len(ready_results),
                "published_count": len(published_results),
                "total_deprecated": stats_by_status.get("Deprecated", 0),
                "actions_count": len(my_actions)
            }
        }

    except Exception as e:
        logger.error(f"Failed to get publisher dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/developer")
async def get_developer_dashboard(developer_address: str, uuid: Optional[str] = None):
    """Dashboard data for AI Developers: their cards, actions needed, and stats."""
    try:
        if not developer_address:
            raise HTTPException(status_code=400, detail="developer_address is required")

        logger.info(f"[Developer Dashboard] Fetching data for address: {developer_address}, uuid: {uuid}")

        addresses_query = """
        // Find addresses via User node (by EOA)
        OPTIONAL MATCH (u:User {eoa_address: $address})
        WITH u, CASE WHEN u IS NOT NULL THEN [u.eoa_address] ELSE [] END AS eoa_addresses

        // Find custom accounts linked to user
        OPTIONAL MATCH (u)-[:HAS_CUSTOM_ACCOUNT]->(ca:CustomAccount)
        WITH u, eoa_addresses, collect(ca.address) AS custom_addresses

        // Also check if address itself is a custom account
        OPTIONAL MATCH (ca2:CustomAccount {address: $address})<-[:HAS_CUSTOM_ACCOUNT]-(u2:User)
        WITH eoa_addresses, custom_addresses, u2, collect(ca2.address) AS ca2_addresses
        WITH eoa_addresses, custom_addresses,
             CASE WHEN u2 IS NOT NULL THEN [u2.eoa_address] + ca2_addresses ELSE [] END AS via_custom

        // Combine all addresses (include original address as fallback)
        WITH eoa_addresses + custom_addresses + via_custom + [$address] AS all_addresses
        UNWIND all_addresses AS addr
        WITH DISTINCT toLower(addr) AS address WHERE address IS NOT NULL
        RETURN collect(address) AS addresses
        """
        addr_results = await neo4j_conn.query(addresses_query, {"address": developer_address})

        user_addresses = []
        if addr_results and len(addr_results) > 0:
            user_addresses = addr_results[0].get("addresses", [developer_address.lower()])
        if not user_addresses:
            user_addresses = [developer_address.lower()]

        logger.info(f"[Developer Dashboard] User addresses: {user_addresses}")

        if uuid:
            cards_query = """
            // Find cards via CREATED relationship
            OPTIONAL MATCH (u:User {uuid: $uuid})-[:CREATED]->(mc_rel:ModelCard)

            // Find cards via creator_uuid field
            OPTIONAL MATCH (mc_uuid:ModelCard {creator_uuid: $uuid})

            // Find cards via address match
            OPTIONAL MATCH (mc_addr:ModelCard)
            WHERE toLower(mc_addr.blockchain_address) IN $addresses
               OR toLower(mc_addr.last_updated_by) IN $addresses

            // Also find cards where user was actor in NFTMinted or NFTSubmitted events
            OPTIONAL MATCH (mc_event:ModelCard)-[:HAS_EVENT]->(evt:StatusEvent)
            WHERE toLower(evt.actor) IN $addresses
              AND evt.action IN ['NFTMinted', 'NFTSubmitted']

            // Combine all found cards
            WITH collect(DISTINCT mc_rel) + collect(DISTINCT mc_uuid) + collect(DISTINCT mc_addr) + collect(DISTINCT mc_event) as all_cards
            UNWIND all_cards as mc
            WITH DISTINCT mc WHERE mc IS NOT NULL

            OPTIONAL MATCH (mc)-[:HAS_EVENT]->(event:StatusEvent)
            WITH mc, count(event) as event_count
            RETURN mc.token_id as token_id,
                   mc.model_name as model_name,
                   mc.current_status as status,
                   mc.version as version,
                   mc.created_at as created_at,
                   mc.developer_organization as organization,
                   event_count,
                   CASE mc.current_status
                       WHEN 'Created' THEN 'needs_submission'
                       WHEN 'RevisionRequested' THEN 'needs_revision'
                       WHEN 'Rejected' THEN 'rejected'
                       WHEN 'Published' THEN 'live'
                       WHEN 'Deprecated' THEN 'archived'
                       ELSE 'in_progress'
                   END as action_needed
            ORDER BY mc.created_at DESC
            """
            cards_results = await neo4j_conn.query(cards_query, {"uuid": uuid, "addresses": user_addresses})
        else:
            cards_query = """
            // Find cards via address fields
            OPTIONAL MATCH (mc_addr:ModelCard)
            WHERE toLower(mc_addr.blockchain_address) IN $addresses
               OR toLower(mc_addr.last_updated_by) IN $addresses

            // Also find cards where user was actor in NFTMinted or NFTSubmitted events
            OPTIONAL MATCH (mc_event:ModelCard)-[:HAS_EVENT]->(evt:StatusEvent)
            WHERE toLower(evt.actor) IN $addresses
              AND evt.action IN ['NFTMinted', 'NFTSubmitted']

            // Combine all found cards
            WITH collect(DISTINCT mc_addr) + collect(DISTINCT mc_event) as all_cards
            UNWIND all_cards as mc
            WITH DISTINCT mc WHERE mc IS NOT NULL

            OPTIONAL MATCH (mc)-[:HAS_EVENT]->(event:StatusEvent)
            WITH mc, count(event) as event_count
            RETURN mc.token_id as token_id,
                   mc.model_name as model_name,
                   mc.current_status as status,
                   mc.version as version,
                   mc.created_at as created_at,
                   mc.developer_organization as organization,
                   event_count,
                   CASE mc.current_status
                       WHEN 'Created' THEN 'needs_submission'
                       WHEN 'RevisionRequested' THEN 'needs_revision'
                       WHEN 'Rejected' THEN 'rejected'
                       WHEN 'Published' THEN 'live'
                       WHEN 'Deprecated' THEN 'archived'
                       ELSE 'in_progress'
                   END as action_needed
            ORDER BY mc.created_at DESC
            """
            cards_results = await neo4j_conn.query(cards_query, {"addresses": user_addresses})

        logger.info(f"[Developer Dashboard] Found {len(cards_results)} cards for address {developer_address} (uuid: {uuid})")

        grouped = {
            "needs_submission": [],
            "needs_revision": [],
            "in_progress": [],
            "live": [],
            "archived": [],
            "rejected": []
        }

        for card in cards_results:
            action = card.get("action_needed", "in_progress")
            if action in grouped:
                grouped[action].append(card)

        return {
            "all_cards": cards_results,
            "grouped": grouped,
            "stats": {
                "total": len(cards_results),
                "needs_attention": len(grouped["needs_submission"]) + len(grouped["needs_revision"]),
                "in_progress": len(grouped["in_progress"]),
                "live": len(grouped["live"]),
                "archived": len(grouped["archived"]),
                "rejected": len(grouped["rejected"])
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get developer dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/lineage/{organization}/{model_name}")
async def get_model_lineage_endpoint(organization: str, model_name: str):
    """Get the complete version lineage for a model across all NFT IDs."""
    try:
        result = await get_model_lineage(organization, model_name)
        return result

    except Exception as e:
        logger.error(f"Failed to get model lineage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-cards/{token_id}/version-chain")
async def get_version_chain_endpoint(token_id: int):
    """Get the predecessor/successor version chain for a specific model card."""
    try:
        result = await get_version_chain(token_id)

        if result.get("error"):
            raise HTTPException(status_code=404, detail=result.get("error"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get version chain: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/model-cards/{token_id}/successor")
async def get_successor(token_id: int):
    """Get the successor of a deprecated model card, if it has been superseded."""
    try:
        query = """
        MATCH (mc:ModelCard {token_id: $token_id})
        OPTIONAL MATCH (successor:ModelCard)-[:SUPERSEDES]->(mc)
        RETURN mc.current_status as status,
               mc.superseded_by as superseded_by,
               successor.token_id as successor_token_id,
               successor.version as successor_version,
               successor.current_status as successor_status
        """

        result = await neo4j_conn.query(query, {"token_id": token_id})

        if not result:
            raise HTTPException(status_code=404, detail="Model card not found")

        data = result[0]

        if data.get("successor_token_id"):
            return {
                "token_id": token_id,
                "has_successor": True,
                "successor": {
                    "token_id": data.get("successor_token_id"),
                    "version": data.get("successor_version"),
                    "status": data.get("successor_status")
                }
            }
        else:
            return {
                "token_id": token_id,
                "has_successor": False,
                "current_status": data.get("status"),
                "message": "This model card has not been superseded" if data.get("status") != "Deprecated" else "This deprecated card has not been superseded yet"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get successor: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-cards/{token_id}/predecessor")
async def get_predecessor(token_id: int):
    """
    Get the predecessor that this model card supersedes (if any).

    Quick lookup to find what deprecated card this version replaced.
    """
    try:
        query = """
        MATCH (mc:ModelCard {token_id: $token_id})
        OPTIONAL MATCH (mc)-[:SUPERSEDES]->(predecessor:ModelCard)
        RETURN mc.supersedes as supersedes,
               predecessor.token_id as predecessor_token_id,
               predecessor.version as predecessor_version,
               predecessor.current_status as predecessor_status
        """

        result = await neo4j_conn.query(query, {"token_id": token_id})

        if not result:
            raise HTTPException(status_code=404, detail="Model card not found")

        data = result[0]

        if data.get("predecessor_token_id"):
            return {
                "token_id": token_id,
                "has_predecessor": True,
                "predecessor": {
                    "token_id": data.get("predecessor_token_id"),
                    "version": data.get("predecessor_version"),
                    "status": data.get("predecessor_status")
                }
            }
        else:
            return {
                "token_id": token_id,
                "has_predecessor": False,
                "message": "This model card does not supersede any previous version"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get predecessor: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query string")
    status: Optional[str] = Field(None, description="Filter by status")
    limit: int = Field(50, ge=1, le=100, description="Maximum results to return")

@router.post("/model-cards/search")
async def search_model_cards(search: SearchRequest):
    """Multi-field search across model cards with relevance scoring."""
    try:
        query_lower = search.query.lower().strip()

        cypher_query = """
        MATCH (mc:ModelCard)
        WHERE (
            toLower(mc.model_name) CONTAINS $query
            OR toLower(mc.description) CONTAINS $query
            OR toLower(mc.developer_organization) CONTAINS $query
            OR toLower(mc.algorithms_used) CONTAINS $query
            OR toLower(mc.clinical_indications) CONTAINS $query
            OR toLower(mc.intended_purpose) CONTAINS $query
            OR toLower(mc.version) CONTAINS $query
            OR toLower(mc.primary_intended_users) CONTAINS $query
            OR toLower(mc.patient_target_group) CONTAINS $query
            OR toString(mc.token_id) CONTAINS $query
        )
        """

        if search.status and search.status != "all":
            cypher_query += " AND mc.current_status = $status"

        cypher_query += """
        WITH mc,
            CASE
                WHEN toLower(mc.model_name) CONTAINS $query THEN 100
                ELSE 0
            END +
            CASE
                WHEN toLower(mc.model_name) STARTS WITH $query THEN 50
                ELSE 0
            END +
            CASE
                WHEN toLower(mc.developer_organization) CONTAINS $query THEN 30
                ELSE 0
            END +
            CASE
                WHEN toLower(mc.description) CONTAINS $query THEN 20
                ELSE 0
            END +
            CASE
                WHEN toLower(mc.algorithms_used) CONTAINS $query THEN 15
                ELSE 0
            END +
            CASE
                WHEN toLower(mc.clinical_indications) CONTAINS $query THEN 10
                ELSE 0
            END AS relevance_score

        RETURN mc.token_id as token_id,
               mc.model_name as model_name,
               mc.version as version,
               mc.developer_organization as developer_organization,
               mc.description as description,
               mc.current_status as current_status,
               mc.created_at as created_at,
               mc.algorithms_used as algorithms_used,
               mc.clinical_indications as clinical_indications,
               mc.intended_purpose as intended_purpose,
               mc.superseded_by as superseded_by,
               mc.supersedes as supersedes,
               relevance_score
        ORDER BY relevance_score DESC, mc.created_at DESC
        LIMIT $limit
        """

        params = {
            "query": query_lower,
            "limit": search.limit
        }
        if search.status and search.status != "all":
            params["status"] = search.status

        results = await neo4j_conn.query(cypher_query, params)

        formatted_results = []
        for r in results:
            result = {
                "token_id": r.get("token_id"),
                "model_name": r.get("model_name"),
                "version": r.get("version"),
                "developer_organization": r.get("developer_organization"),
                "description": r.get("description"),
                "current_status": r.get("current_status"),
                "created_at": r.get("created_at"),
                "algorithms_used": r.get("algorithms_used"),
                "clinical_indications": r.get("clinical_indications"),
                "intended_purpose": r.get("intended_purpose"),
                "superseded_by": r.get("superseded_by"),
                "supersedes": r.get("supersedes"),
                "relevance_score": r.get("relevance_score", 0),
                "match_fields": []
            }

            if r.get("model_name") and query_lower in r.get("model_name", "").lower():
                result["match_fields"].append("model_name")
            if r.get("description") and query_lower in r.get("description", "").lower():
                result["match_fields"].append("description")
            if r.get("developer_organization") and query_lower in r.get("developer_organization", "").lower():
                result["match_fields"].append("developer_organization")
            if r.get("algorithms_used") and query_lower in r.get("algorithms_used", "").lower():
                result["match_fields"].append("algorithms_used")
            if r.get("clinical_indications") and query_lower in r.get("clinical_indications", "").lower():
                result["match_fields"].append("clinical_indications")

            formatted_results.append(result)

        return {
            "query": search.query,
            "status_filter": search.status,
            "total_results": len(formatted_results),
            "results": formatted_results
        }

    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")



class ChallengeRequest(BaseModel):
    reason: str = Field(..., description="One of REPUDIATION_REASONS")
    challenger_address: Optional[str] = Field(
        None,
        description="EOA or smart account of the challenger. Used to enforce "
                    "separation of duties - you cannot challenge an action you "
                    "performed yourself, nor any action on a card you created."
    )


class ResolveRequest(BaseModel):
    final_status: str = Field(..., description="ResolvedValid or ResolvedInvalid")


@router.get("/model-cards/{token_id}/governance")
async def get_card_governance(token_id: int):
    """Full governance read for a card: state, action records, reason."""
    try:
        return get_governance(token_id)
    except Exception as exc:
        logger.error(f"governance read failed for token {token_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/model-cards/{token_id}/actions")
async def get_card_actions(token_id: int):
    """Action history for a card (one record per state transition)."""
    try:
        return {"token_id": token_id, "actions": get_actions_for_token(token_id)}
    except Exception as exc:
        logger.error(f"action read failed for token {token_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/identity/claim/{address}")
async def get_identity_claim(address: str, claim_type: int = 2):
    """Resolve the actor's current best claim of claim_type (1=developer, 2=authenticator, 3=publisher)."""
    try:
        return get_claim_status(address, claim_type)
    except Exception as exc:
        logger.error(f"claim read failed for {address}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/identity/actions/by-actor/{address}")
async def get_actor_actions(address: str, status: Optional[str] = None, limit: int = 100):
    """Per-actor action history, optionally filtered to one IdentityStatus."""
    statuses = [status] if status else None
    try:
        return {
            "actor": address,
            "status_filter": status,
            "actions": list_actions_for_actor(address, statuses=statuses, limit=limit),
        }
    except Exception as exc:
        logger.error(f"actor action read failed for {address}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/governance/disputes")
async def list_open_disputes(limit: int = 200, admin: str = Depends(verify_admin_token)):
    """Arbiter queue: all currently-Disputed actions across all tokens. Admin-only."""
    try:
        return {"disputes": list_disputed_actions(limit=limit)}
    except Exception as exc:
        logger.error(f"dispute list failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/governance/repudiation-reasons")
async def get_repudiation_reasons():
    return {"reasons": REPUDIATION_REASONS}


@router.get("/model-cards/{token_id}/export")
async def export_model_card(token_id: int, format: str = "json"):
    """Export a model card via smart_model_card.exporters (format: json | md | html)."""
    if format not in ("json", "md", "html"):
        raise HTTPException(status_code=400, detail="format must be json, md, or html")

    rows = await neo4j_conn.query(
        "MATCH (mc:ModelCard {token_id: $token_id}) RETURN mc.full_metadata AS meta, mc.model_name AS name",
        {"token_id": token_id},
    )
    if not rows or not rows[0].get("meta"):
        raise HTTPException(status_code=404, detail="Model card not found")

    raw = rows[0]["meta"]
    try:
        metadata = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        raise HTTPException(status_code=500, detail="Could not parse model card metadata")

    import os, tempfile, re
    from fastapi.responses import FileResponse, Response
    from smart_model_card import ModelCard
    from smart_model_card.exporters import JSONExporter, MarkdownExporter, HTMLExporter

    try:
        card = ModelCard.from_dict(metadata)
    except Exception as exc:
        logger.error("ModelCard.from_dict failed for token %s: %s", token_id, exc)
        raise HTTPException(status_code=500, detail=f"Could not reconstruct card: {exc}")

    name = rows[0].get("name") or f"card-{token_id}"
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(name)).strip("-").lower() or f"card-{token_id}"
    filename = f"{slug}.{format}"

    suffix_map = {"json": ".json", "md": ".md", "html": ".html"}
    media_map = {
        "json": "application/json",
        "md": "text/markdown",
        "html": "text/html",
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix_map[format], delete=False, encoding="utf-8") as tmp:
        tmp_path = tmp.name

    try:
        if format == "json":
            JSONExporter.export(card, tmp_path)
        elif format == "md":
            MarkdownExporter.export(card, tmp_path)
        else:
            HTMLExporter.export(card, tmp_path)
        with open(tmp_path, "r", encoding="utf-8") as fh:
            body = fh.read()
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    return Response(
        content=body,
        media_type=media_map[format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/model-cards/{token_id}/visualizations")
async def get_model_card_visualizations(token_id: int):
    """Render the model card's metadata into base64-PNG charts."""
    rows = await neo4j_conn.query(
        "MATCH (mc:ModelCard {token_id: $token_id}) RETURN mc.full_metadata AS meta",
        {"token_id": token_id},
    )
    if not rows or not rows[0].get("meta"):
        raise HTTPException(status_code=404, detail="Model card metadata not found")

    raw = rows[0]["meta"]
    try:
        metadata = json.loads(raw) if isinstance(raw, str) else raw
    except Exception as exc:
        logger.error("could not parse metadata for token %s: %s", token_id, exc)
        raise HTTPException(status_code=500, detail="Could not parse model card metadata")

    from app.utils.model_card_viz import build_visualizations
    try:
        viz = build_visualizations(metadata)
    except Exception as exc:
        logger.error("build_visualizations failed for token %s: %s", token_id, exc)
        raise HTTPException(status_code=500, detail=f"Visualization generation failed: {exc}")

    return {
        "token_id": token_id,
        "count": len(viz),
        "visualizations": viz,
    }


@router.post("/actions/{action_id}/challenge")
async def challenge_action_endpoint(action_id: int, body: ChallengeRequest):
    """Mark an ActionRecord as Disputed (reason in REPUDIATION_REASONS); enforces separation of duties."""
    try:
        if not body.challenger_address:
            raise HTTPException(
                status_code=400,
                detail="challenger_address is required so the platform can verify you are not challenging your own action.",
            )
        challenger_uuid = await neo4j_conn.get_uuid_for_address(body.challenger_address)
        if not challenger_uuid:
            raise HTTPException(
                status_code=403,
                detail="Could not identify your account - sign in again and retry.",
            )

        from app.utils.identity_binding import _lifecycle, _decode_action
        try:
            raw = _lifecycle().functions.getAction(int(action_id)).call()
            action = _decode_action(raw)
        except Exception as exc:
            logger.warning(f"SoD pre-check could not read action {action_id}: {exc}")
            raise HTTPException(status_code=500, detail="Could not verify SoD pre-conditions.")

        actor_uuid = await neo4j_conn.get_uuid_for_address(action.get("actor") or "")
        if actor_uuid and actor_uuid == challenger_uuid:
            raise HTTPException(
                status_code=403,
                detail="You performed this action - you cannot challenge it yourself.",
            )
        challenger_eoa: Optional[str] = None
        if body.challenger_address:
            user = await neo4j_conn.get_user_by_uuid(challenger_uuid)
            challenger_eoa = (user or {}).get("eoa_address")
        result = challenge_action(action_id, body.reason, challenger=challenger_eoa)
        result["panel_drawn"] = False
        result["panel_warning"] = None

        try:
            from app.utils.identity_binding import _lifecycle, _decode_action
            action = _decode_action(_lifecycle().functions.getAction(int(action_id)).call())
            token_id = action.get("token_id")
            case_id = await neo4j_conn.open_dispute_case(
                action_id=action_id, token_id=token_id,
                challenger_uuid=challenger_uuid, kind="action",
            )
            existing = await neo4j_conn.get_dispute_case(case_id)
            if not existing or len(existing.get("panel") or []) < 2:
                reviewers = await neo4j_conn.get_eligible_arbiters(token_id, challenger_uuid, "Reviewer")
                publishers = await neo4j_conn.get_eligible_arbiters(token_id, challenger_uuid, "Publisher")
                if reviewers and publishers:
                    chosen_reviewer = _random.choice(reviewers)
                    chosen_publisher = _random.choice(publishers)
                    await neo4j_conn.assign_panel_member(case_id, chosen_reviewer["uuid"], "Reviewer")
                    await neo4j_conn.assign_panel_member(case_id, chosen_publisher["uuid"], "Publisher")
                    logger.info(
                        f"Auto-drew panel for action {action_id}: "
                        f"reviewer={chosen_reviewer['uuid'][:8]}, publisher={chosen_publisher['uuid'][:8]}"
                    )
                    result["panel_drawn"] = True
                else:
                    missing = []
                    if not reviewers: missing.append("Reviewer")
                    if not publishers: missing.append("Publisher")
                    msg = (
                        f"Challenge recorded on chain. Panel could not be drawn yet - "
                        f"no eligible {' / '.join(missing)} on file. "
                        f"An admin must promote one before the dispute can be resolved."
                    )
                    logger.info(msg)
                    result["panel_warning"] = msg
        except Exception as exc:
            logger.warning(f"Auto-draw panel failed for action {action_id}: {exc}")

        return result
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"challengeAction({action_id}) failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))



import random as _random


class PanelDrawRequest(BaseModel):
    challenger_address: Optional[str] = None


class PanelSetRequest(BaseModel):
    reviewer_uuid: str
    publisher_uuid: str
    challenger_address: Optional[str] = None


class PanelVoteRequest(BaseModel):
    voter_address: str
    vote: str
    signature: Optional[str] = Field(
        None,
        description=(
            "Hex-encoded signature over the on-chain panel-vote digest. "
            "Required when the contract enforces 2-of-N quorum. "
            "If absent, the backend records the vote as session-trust only "
            "(legacy mode for prototype demos)."
        ),
    )


class PanelVoteDigestRequest(BaseModel):
    final_status: str


@router.post("/disputes/{action_id}/digest")
async def get_panel_vote_digest(action_id: int, body: PanelVoteDigestRequest):
    """Return the canonical digest a panel member must sign to vote final_status on this action."""
    try:
        from app.utils.identity_binding import panel_vote_digest
        final_status = (
            "ResolvedValid" if body.final_status in ("Upheld", "ResolvedValid")
            else "ResolvedInvalid"
        )
        return {
            "action_id": action_id,
            "final_status": final_status,
            "digest": "0x" + panel_vote_digest(action_id, final_status),
        }
    except Exception as exc:
        logger.error(f"panel-vote-digest({action_id}) failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/disputes/{action_id}/eligible-arbiters")
async def list_eligible_arbiters(action_id: int, challenger: Optional[str] = None):
    """Return eligible Reviewers and Publishers for a dispute, excluding creator/actors/challenger."""
    try:
        from app.utils.identity_binding import _lifecycle, _decode_action
        action = _decode_action(_lifecycle().functions.getAction(int(action_id)).call())
        token_id = action.get("token_id")
        challenger_uuid = (
            await neo4j_conn.get_uuid_for_address(challenger) if challenger else None
        )
        reviewers = await neo4j_conn.get_eligible_arbiters(token_id, challenger_uuid, "Reviewer")
        publishers = await neo4j_conn.get_eligible_arbiters(token_id, challenger_uuid, "Publisher")
        return {
            "action_id": action_id,
            "token_id": token_id,
            "reviewers": reviewers,
            "publishers": publishers,
        }
    except Exception as exc:
        logger.error(f"eligible-arbiters({action_id}) failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/disputes/{action_id}/draw-panel")
async def draw_dispute_panel(action_id: int, body: PanelDrawRequest):
    """Draw one Reviewer and one Publisher and open a :DisputeCase, or return the existing case."""
    try:
        from app.utils.identity_binding import _lifecycle, _decode_action
        action = _decode_action(_lifecycle().functions.getAction(int(action_id)).call())
        token_id = action.get("token_id")
        challenger_uuid = (
            await neo4j_conn.get_uuid_for_address(body.challenger_address)
            if body.challenger_address else None
        )

        case_id = await neo4j_conn.open_dispute_case(
            action_id=action_id,
            token_id=token_id,
            challenger_uuid=challenger_uuid,
            kind="action",
        )

        existing = await neo4j_conn.get_dispute_case(case_id)
        if existing and len(existing.get("panel") or []) >= 2:
            return {"case": existing, "drawn": False}

        reviewers = await neo4j_conn.get_eligible_arbiters(token_id, challenger_uuid, "Reviewer")
        publishers = await neo4j_conn.get_eligible_arbiters(token_id, challenger_uuid, "Publisher")
        if not reviewers or not publishers:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Cannot draw panel - no eligible "
                    f"{'Reviewer' if not reviewers else 'Publisher'} on file. "
                    "Admin must override via /set-panel."
                ),
            )

        chosen_reviewer = _random.choice(reviewers)
        chosen_publisher = _random.choice(publishers)
        await neo4j_conn.assign_panel_member(case_id, chosen_reviewer["uuid"], "Reviewer")
        await neo4j_conn.assign_panel_member(case_id, chosen_publisher["uuid"], "Publisher")

        return {"case": await neo4j_conn.get_dispute_case(case_id), "drawn": True}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"draw-panel({action_id}) failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/disputes/{action_id}/candidates")
async def list_panel_candidates(action_id: int, admin: str = Depends(verify_admin_token)):
    """Return eligible Reviewers and Publishers for an action (admin panel selection)."""
    try:
        from app.utils.identity_binding import _lifecycle, _decode_action
        action = _decode_action(_lifecycle().functions.getAction(int(action_id)).call())
        token_id = action.get("token_id")
        challenger_addr = (action.get("challenger_onchain") or "").lower()
        challenger_uuid = (
            await neo4j_conn.get_uuid_for_address(challenger_addr) if challenger_addr else None
        )
        reviewers = await neo4j_conn.get_eligible_arbiters(token_id, challenger_uuid, "Reviewer")
        publishers = await neo4j_conn.get_eligible_arbiters(token_id, challenger_uuid, "Publisher")
        return {
            "action_id": action_id,
            "token_id": token_id,
            "challenger_uuid": challenger_uuid,
            "reviewers": reviewers,
            "publishers": publishers,
            "note": (
                "Pick one Reviewer and one Publisher. They must be different "
                "people on chain (distinct EOAs). Both must hold an active "
                "institutional claim of the right type. If either pool is "
                "empty, you can't form a panel - promote more users first."
            ),
        }
    except Exception as exc:
        logger.error(f"list_panel_candidates({action_id}) failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/disputes/{action_id}/set-panel")
async def set_dispute_panel(
    action_id: int,
    body: PanelSetRequest,
    admin: str = Depends(verify_admin_token),
):
    """Admin-only: assign panel members for a dispute case (selection only; the panel decides)."""
    try:
        from app.utils.identity_binding import _lifecycle, _decode_action, get_claim_status
        action = _decode_action(_lifecycle().functions.getAction(int(action_id)).call())
        token_id = action.get("token_id")
        challenger_uuid = (
            await neo4j_conn.get_uuid_for_address(body.challenger_address)
            if body.challenger_address else None
        )
        case_id = await neo4j_conn.open_dispute_case(
            action_id=action_id, token_id=token_id,
            challenger_uuid=challenger_uuid, kind="action",
        )

        if body.reviewer_uuid == body.publisher_uuid:
            raise HTTPException(
                status_code=400,
                detail="Reviewer and Publisher must be different users.",
            )

        rev_user = await neo4j_conn.get_user_by_uuid(body.reviewer_uuid)
        pub_user = await neo4j_conn.get_user_by_uuid(body.publisher_uuid)
        if not rev_user or not pub_user:
            raise HTTPException(status_code=404, detail="One or both panel members not found.")
        rev_eoa = (rev_user.get("eoa_address") or "").lower()
        pub_eoa = (pub_user.get("eoa_address") or "").lower()
        if not rev_eoa or not pub_eoa:
            raise HTTPException(status_code=400, detail="Panel members are missing EOA addresses on file.")
        if rev_eoa == pub_eoa:
            raise HTTPException(
                status_code=400,
                detail="Reviewer and Publisher must use distinct EOA addresses on chain.",
            )

        actors_record = await neo4j_conn.get_card_actors(token_id)
        creator_uuid = actors_record.get("creator_uuid")
        prior = []
        for ev in actors_record.get("events") or []:
            if ev.get("actor"):
                u = await neo4j_conn.get_uuid_for_address(ev["actor"])
                if u:
                    prior.append(u)
        excluded = set(filter(None, prior + [creator_uuid, challenger_uuid]))
        for uid, label in (
            (body.reviewer_uuid, "Reviewer"),
            (body.publisher_uuid, "Publisher"),
        ):
            if uid in excluded:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"{label} ({uid[:8]}…) is excluded from this panel - they are the "
                        f"card creator, a prior actor on it, or the original challenger."
                    ),
                )

        rev_claim = get_claim_status(rev_user.get("eoa_address"), 2)
        if not (rev_claim.get("has_claim") and rev_claim.get("attestation_level") == "institutional"):
            raise HTTPException(
                status_code=400,
                detail="Reviewer must hold an active institutional Reviewer claim on chain.",
            )
        pub_claim = get_claim_status(pub_user.get("eoa_address"), 3)
        if not (pub_claim.get("has_claim") and pub_claim.get("attestation_level") == "institutional"):
            raise HTTPException(
                status_code=400,
                detail="Publisher must hold an active institutional Publisher claim on chain.",
            )

        await neo4j_conn.assign_panel_member(case_id, body.reviewer_uuid, "Reviewer")
        await neo4j_conn.assign_panel_member(case_id, body.publisher_uuid, "Publisher")

        return {"case": await neo4j_conn.get_dispute_case(case_id)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"set-panel({action_id}) failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/disputes/{action_id}/vote")
async def vote_on_dispute(action_id: int, body: PanelVoteRequest):
    """Panel member submits a vote; two matching cross-role votes trigger on-chain resolution."""
    if body.vote not in ("Upheld", "Repudiated"):
        raise HTTPException(status_code=400, detail="vote must be 'Upheld' or 'Repudiated'.")

    case_id = f"dc_action_{int(action_id)}"
    try:
        voter_uuid = await neo4j_conn.get_uuid_for_address(body.voter_address)
        if not voter_uuid:
            raise HTTPException(status_code=403, detail="Unknown voter address.")

        case = await neo4j_conn.get_dispute_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="No panel has been drawn for this dispute yet.")

        panel_uuids = {m.get("uuid"): m for m in (case.get("panel") or [])}
        if voter_uuid not in panel_uuids:
            raise HTTPException(status_code=403, detail="You are not a panel member for this dispute.")

        signature_to_store = body.signature
        signer_eoa = body.voter_address
        try:
            if body.signature:
                hex_no_prefix = body.signature[2:] if body.signature.startswith("0x") else body.signature
                if len(hex_no_prefix) == 64:
                    from app.utils.blockchain import get_private_key_for_user, sign_message
                    user = await neo4j_conn.get_user_by_uuid(voter_uuid)
                    eoa = (user or {}).get("eoa_address")
                    if eoa:
                        priv = await get_private_key_for_user(eoa)
                        if priv:
                            sig = sign_message(priv, bytes.fromhex(hex_no_prefix))
                            signature_to_store = sig if sig.startswith("0x") else "0x" + sig
                            signer_eoa = eoa
        except Exception as exc:
            logger.warning(f"server-side digest signing failed: {exc}")

        updated = await neo4j_conn.record_panel_vote(
            case_id,
            voter_uuid,
            body.vote,
            signature=signature_to_store,
            signer_address=signer_eoa,
        )
        panel = updated.get("panel") if updated else []
        votes = [m.get("vote") for m in panel if m.get("vote")]

        finalised = False
        outcome = None
        on_chain_tx = None
        if len([v for v in votes if v]) >= 2:
            if all(v == votes[0] for v in votes if v):
                outcome = votes[0]
                final_status = "ResolvedValid" if outcome == "Upheld" else "ResolvedInvalid"

                signed_members = [m for m in panel if m.get("signature") and m.get("signer_address")]
                try:
                    if len(signed_members) >= 2:
                        rev = next((m for m in signed_members if m.get("role_class") == "Reviewer"), None)
                        pub = next((m for m in signed_members if m.get("role_class") == "Publisher"), None)
                        if rev and pub:
                            from app.utils.identity_binding import resolve_dispute_quorum
                            res = resolve_dispute_quorum(
                                action_id, final_status,
                                rev["signer_address"], rev["signature"],
                                pub["signer_address"], pub["signature"],
                            )
                            on_chain_tx = res.get("tx_hash")
                        else:
                            res = resolve_dispute(action_id, final_status)
                            on_chain_tx = res.get("tx_hash")
                    else:
                        res = resolve_dispute(action_id, final_status)
                        on_chain_tx = res.get("tx_hash")
                    await neo4j_conn.close_dispute_case(case_id, outcome)
                    finalised = True
                except Exception as exc:
                    logger.error(f"resolve on-chain call failed for action {action_id}: {exc}")
                    raise HTTPException(
                        status_code=502,
                        detail=f"Panel agreed but on-chain resolution failed: {exc}",
                    )
            else:
                await neo4j_conn.close_dispute_case(case_id, "Split")

        return {
            "case_id": case_id,
            "panel": panel,
            "finalised": finalised,
            "outcome": outcome,
            "on_chain_tx": on_chain_tx,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"vote-on-dispute({action_id}) failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/governance/dispute-cases")
async def list_dispute_cases(
    status: Optional[str] = None,
    outcome: Optional[str] = None,
    admin: str = Depends(verify_admin_token),
):
    """Admin queue: all off-chain dispute cases, optionally filtered by status or outcome."""
    where = []
    params: Dict[str, Any] = {}
    if status:
        where.append("dc.status = $status")
        params["status"] = status
    if outcome:
        where.append("dc.outcome = $outcome")
        params["outcome"] = outcome
    where_clause = (" WHERE " + " AND ".join(where)) if where else ""
    query = f"""
    MATCH (dc:DisputeCase){where_clause}
    OPTIONAL MATCH (dc)-[r:HAS_PANEL_MEMBER]->(u:User)
    RETURN dc.case_id AS case_id, dc.action_id AS action_id, dc.token_id AS token_id,
           dc.kind AS kind, dc.status AS status, dc.outcome AS outcome,
           dc.challenger_uuid AS challenger_uuid,
           dc.created_at AS created_at, dc.closed_at AS closed_at,
           collect({{
             uuid: u.uuid, username: u.username,
             role_class: r.role_class, vote: r.vote,
             voted_at: r.voted_at
           }}) AS panel
    ORDER BY dc.created_at DESC
    """
    rows = await neo4j_conn.query(query, params)
    return {"cases": rows}


@router.get("/disputes/mine")
async def my_open_panels(actor: str):
    """Return open dispute cases where actor is on the panel and hasn't voted yet."""
    voter_uuid = await neo4j_conn.get_uuid_for_address(actor)
    if not voter_uuid:
        return {"actor_uuid": None, "cases": []}
    rows = await neo4j_conn.query(
        """
        MATCH (dc:DisputeCase {status: 'open'})-[r:HAS_PANEL_MEMBER]->(u:User {uuid: $uuid})
        OPTIONAL MATCH (dc)-[r2:HAS_PANEL_MEMBER]->(other:User)
        RETURN dc.case_id AS case_id, dc.action_id AS action_id, dc.token_id AS token_id,
               dc.kind AS kind, dc.created_at AS created_at,
               r.role_class AS my_role_class, r.vote AS my_vote,
               collect({uuid: other.uuid, username: other.username,
                        role_class: r2.role_class, vote: r2.vote}) AS panel
        ORDER BY dc.created_at DESC
        """,
        {"uuid": voter_uuid},
    )
    return {"actor_uuid": voter_uuid, "cases": rows}


@router.get("/disputes/{action_id}/case")
async def get_dispute_case_endpoint(action_id: int):
    """Return the off-chain :DisputeCase (panel, votes, outcome) for the given action."""
    case_id = f"dc_action_{int(action_id)}"
    case = await neo4j_conn.get_dispute_case(case_id)
    if not case:
        return {"case_id": case_id, "exists": False}
    return {"exists": True, **case}


@router.post("/actions/{action_id}/resolve")
async def resolve_action_endpoint(
    action_id: int,
    body: ResolveRequest,
    admin: str = Depends(verify_admin_token),
):
    """Emergency-only single-key resolution for old cases where no panel can be formed."""
    EMERGENCY_AGE_DAYS = 14
    case_id = f"dc_action_{int(action_id)}"
    case = await neo4j_conn.get_dispute_case(case_id)

    if case:
        panel = case.get("panel") or []
        members_with_uuid = [m for m in panel if m.get("uuid")]
        votes_cast = [m for m in members_with_uuid if m.get("vote")]
        case_status = case.get("status")
        case_outcome = case.get("outcome")

        is_split = case_status == "closed" and case_outcome == "Split"

        if not is_split:
            if members_with_uuid and len(votes_cast) < len(members_with_uuid):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Panel members are still voting. Admin cannot "
                        "override an in-progress vote. If a panel member is "
                        "unresponsive, reassign that seat via /set-panel."
                    ),
                )
            if case_status == "closed" and case_outcome in ("Upheld", "Repudiated"):
                raise HTTPException(
                    status_code=409,
                    detail=f"This dispute is already resolved ({case_outcome}).",
                )
            if not members_with_uuid:
                created_at = case.get("created_at") or 0
                try:
                    from time import time as _time
                    age_days = max(0.0, (_time() * 1000 - int(created_at)) / 86_400_000)
                except Exception:
                    age_days = 0.0
                if age_days < EMERGENCY_AGE_DAYS:
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            f"This dispute is {age_days:.1f} days old. "
                            f"Single-key admin resolution is only allowed "
                            f"after {EMERGENCY_AGE_DAYS} days AND when no "
                            f"panel can be formed. Assign a panel via "
                            f"/set-panel instead."
                        ),
                    )

    try:
        result = resolve_dispute(action_id, body.final_status)
        if case:
            outcome_label = "Upheld" if body.final_status == "ResolvedValid" else "Repudiated"
            await neo4j_conn.close_dispute_case(case_id, outcome_label)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"resolveDispute({action_id}) failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))



class ClaimRequestCreate(BaseModel):
    uuid: str = Field(..., description="Requesting user's UUID")
    claim_type: int = Field(..., ge=1, le=5)
    institution: str = Field(..., min_length=2, max_length=200)
    supporting_url: Optional[str] = None
    note: Optional[str] = Field(None, max_length=500)


class ClaimRequestRejection(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)


async def _resolve_user_eoa(user_uuid: str) -> Optional[str]:
    """Look up the EOA for a UUID via the existing user record."""
    rows = await neo4j_conn.query(
        "MATCH (u:User {uuid: $uuid}) RETURN u.eoa_address AS eoa",
        {"uuid": user_uuid},
    )
    return rows[0]["eoa"] if rows else None


@router.post("/identity/claim-requests")
async def create_claim_request(body: ClaimRequestCreate):
    """User-facing: request an institutional attestation upgrade."""
    eoa = await _resolve_user_eoa(body.uuid)
    if not eoa:
        raise HTTPException(status_code=404, detail="User not found")

    existing = await neo4j_conn.query(
        """
        MATCH (cr:ClaimRequest {uuid: $uuid, claim_type: $claim_type, status: 'pending'})
        RETURN cr.request_id AS request_id LIMIT 1
        """,
        {"uuid": body.uuid, "claim_type": body.claim_type},
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"You already have a pending request for {CLAIM_TYPE_NAMES.get(body.claim_type, 'this claim type')}.",
        )

    request_id = str(_uuid.uuid4())
    await neo4j_conn.execute(
        """
        CREATE (cr:ClaimRequest {
            request_id: $request_id,
            uuid: $uuid,
            eoa: $eoa,
            claim_type: $claim_type,
            institution: $institution,
            supporting_url: $supporting_url,
            note: $note,
            status: 'pending',
            created_at: datetime()
        })
        """,
        {
            "request_id": request_id,
            "uuid": body.uuid,
            "eoa": eoa,
            "claim_type": body.claim_type,
            "institution": body.institution,
            "supporting_url": body.supporting_url,
            "note": body.note,
        },
    )
    return {"request_id": request_id, "status": "pending"}


@router.get("/identity/claim-requests/mine")
async def list_my_claim_requests(uuid: str):
    rows = await neo4j_conn.query(
        """
        MATCH (cr:ClaimRequest {uuid: $uuid})
        RETURN cr ORDER BY cr.created_at DESC
        """,
        {"uuid": uuid},
    )
    out = []
    for r in rows:
        cr = dict(r["cr"])
        cr["created_at"] = str(cr.get("created_at"))
        if cr.get("resolved_at"):
            cr["resolved_at"] = str(cr["resolved_at"])
        if cr.get("claim_type") in CLAIM_TYPE_NAMES:
            cr["claim_type_name"] = CLAIM_TYPE_NAMES[cr["claim_type"]]
        out.append(cr)
    return {"requests": out}


@router.get("/identity/claim-requests/admin")
async def list_all_claim_requests(
    status_filter: str = "pending",
    admin: str = Depends(verify_admin_token),
):
    """Arbiter queue. Filter values: pending | approved | rejected | all. Admin-only."""
    if status_filter == "all":
        cypher = "MATCH (cr:ClaimRequest) RETURN cr ORDER BY cr.created_at DESC"
        params = {}
    else:
        cypher = "MATCH (cr:ClaimRequest {status: $status}) RETURN cr ORDER BY cr.created_at DESC"
        params = {"status": status_filter}
    rows = await neo4j_conn.query(cypher, params)
    out = []
    for r in rows:
        cr = dict(r["cr"])
        cr["created_at"] = str(cr.get("created_at"))
        if cr.get("resolved_at"):
            cr["resolved_at"] = str(cr["resolved_at"])
        if cr.get("claim_type") in CLAIM_TYPE_NAMES:
            cr["claim_type_name"] = CLAIM_TYPE_NAMES[cr["claim_type"]]
        out.append(cr)
    return {"requests": out, "filter": status_filter}


@router.post("/identity/claim-requests/{request_id}/approve")
async def approve_claim_request(
    request_id: str,
    admin: str = Depends(verify_admin_token),
):
    """Admin-only: approve and issue an institutional claim on chain."""
    rows = await neo4j_conn.query(
        "MATCH (cr:ClaimRequest {request_id: $rid}) RETURN cr",
        {"rid": request_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Request not found")
    cr = dict(rows[0]["cr"])
    if cr.get("status") != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {cr.get('status')}")

    try:
        result = issue_claim(
            cr["eoa"],
            int(cr["claim_type"]),
            self_attested=False,
            role=None,
            institution=cr.get("institution"),
            valid_until=0,
        )
    except Exception as exc:
        logger.error("approve_claim_request issue_claim failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"On-chain issuance failed: {exc}")

    await neo4j_conn.execute(
        """
        MATCH (cr:ClaimRequest {request_id: $rid})
        SET cr.status = 'approved',
            cr.resolved_at = datetime(),
            cr.on_chain_tx_hash = $tx
        """,
        {"rid": request_id, "tx": result["tx_hash"]},
    )
    return {"request_id": request_id, "status": "approved", "tx_hash": result["tx_hash"]}


@router.post("/identity/claim-requests/{request_id}/reject")
async def reject_claim_request(
    request_id: str,
    body: ClaimRequestRejection,
    admin: str = Depends(verify_admin_token),
):
    rows = await neo4j_conn.query(
        "MATCH (cr:ClaimRequest {request_id: $rid}) RETURN cr",
        {"rid": request_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Request not found")
    cr = dict(rows[0]["cr"])
    if cr.get("status") != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {cr.get('status')}")

    await neo4j_conn.execute(
        """
        MATCH (cr:ClaimRequest {request_id: $rid})
        SET cr.status = 'rejected',
            cr.resolved_at = datetime(),
            cr.rejection_reason = $reason
        """,
        {"rid": request_id, "reason": body.reason},
    )
    return {"request_id": request_id, "status": "rejected"}



from app.utils.lineage import (
    get_line,
    get_version,
    list_disputed_versions,
    challenge_version,
    resolve_version,
    RELATION_NAMES,
    ENVELOPE_STATUS_NAMES,
)


class VersionChallengeRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)
    challenger_address: Optional[str] = Field(
        None,
        description="EOA or smart account of the challenger. Used to enforce "
                    "separation of duties - you cannot challenge an envelope "
                    "claim on a card you created."
    )


class VersionResolveRequest(BaseModel):
    final_status: str = Field(..., description="Upheld or Repudiated")


@router.get("/lines/{name}")
async def get_line_endpoint(name: str):
    """Full lineage view for a named line: alias, controller, envelope, and versions."""
    try:
        return get_line(name)
    except Exception as exc:
        logger.error("lineage read failed for line '%s': %s", name, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/versions/{token_id}")
async def get_version_endpoint(token_id: int):
    """Single decoded VersionRecord (token_id=0 means no lineage on file)."""
    try:
        return get_version(token_id)
    except Exception as exc:
        logger.error("version read failed for token %s: %s", token_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/governance/envelope-disputes")
async def list_envelope_disputes(
    limit: int = 200,
    admin: str = Depends(verify_admin_token),
):
    """Arbiter queue: versions whose withinEnvelope claim is disputed (admin-only)."""
    try:
        return {"disputes": list_disputed_versions(limit=limit)}
    except Exception as exc:
        logger.error("envelope dispute list failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/governance/lineage-enums")
async def get_lineage_enums():
    """Surface the on-chain enums for frontend dropdowns."""
    return {"relations": RELATION_NAMES, "envelope_statuses": ENVELOPE_STATUS_NAMES}


@router.get("/governance/arbiter")
async def get_arbiter():
    """Return who currently holds the arbiter role on chain."""
    import os
    relayer_pk = os.getenv("RELAYER_PRIVATE_KEY") or os.getenv("PRIVATE_KEY")
    address = None
    if relayer_pk:
        try:
            from eth_account import Account
            address = Account.from_key(relayer_pk).address
        except Exception:
            address = None
    return {
        "address": address,
        "role": "platform_admin",
        "note": (
            "In the current prototype the arbiter is the platform deployer's "
            "key - the same address the relayer uses to forward transactions. "
            "Production deployments are expected to delegate this role to a "
            "multi-sig or accredited notified body."
        ),
    }


@router.post("/versions/{token_id}/challenge")
async def challenge_version_endpoint(token_id: int, body: VersionChallengeRequest):
    """Challenge a withinEnvelope=true claim; the card creator cannot challenge their own card."""
    try:
        if not body.challenger_address:
            raise HTTPException(
                status_code=400,
                detail="challenger_address is required so the platform can verify you are not challenging your own card.",
            )
        challenger_uuid = await neo4j_conn.get_uuid_for_address(body.challenger_address)
        if not challenger_uuid:
            raise HTTPException(
                status_code=403,
                detail="Could not identify your account - sign in again and retry.",
            )
        actors_record = await neo4j_conn.get_card_actors(int(token_id))
        creator_uuid = actors_record.get("creator_uuid")
        if creator_uuid and creator_uuid == challenger_uuid:
            raise HTTPException(
                status_code=403,
                detail="You created this model card. Someone else must challenge its envelope claim.",
            )
        return challenge_version(token_id, body.reason)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("challengeEnvelope(%s) failed: %s", token_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/versions/{token_id}/resolve")
async def resolve_version_endpoint(
    token_id: int,
    body: VersionResolveRequest,
    admin: str = Depends(verify_admin_token),
):
    """Arbiter resolves a Disputed envelope claim. Admin JWT required."""
    try:
        return resolve_version(token_id, body.final_status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("resolveEnvelope(%s) failed: %s", token_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))



class LineageCreateRequest(BaseModel):
    creator_address: str
    line_name: str = Field(..., min_length=1, max_length=200)
    metadata_uri: str
    content_hash_hex: str
    relation: int = Field(0, ge=0, le=5, description="0=Patch ... 5=Withdrawal")
    supersedes: int = Field(0, ge=0)
    within_envelope: bool = False
    envelope_text: Optional[str] = None


@router.post("/model-cards/create-with-lineage")
async def create_model_card_with_lineage_endpoint(body: LineageCreateRequest):
    """Mint a card, claim/update its line, record the version, and optionally pin an envelope."""
    from app.utils.blockchain import (
        pin_line_envelope_on_chain,
        create_model_card_with_lineage_on_chain,
    )
    try:
        ch_hex = body.content_hash_hex.lower().lstrip("0x")
        if len(ch_hex) != 64:
            raise HTTPException(status_code=400, detail="content_hash_hex must be 32 bytes hex")
        content_hash = bytes.fromhex(ch_hex)

        envelope_tx = None
        if body.envelope_text and body.supersedes == 0:
            from web3 import Web3
            envelope_hash = Web3.keccak(text=body.envelope_text)
            envelope_tx = await pin_line_envelope_on_chain(
                body.line_name, envelope_hash, body.creator_address
            )

        result = await create_model_card_with_lineage_on_chain(
            creator=body.creator_address,
            name=body.line_name,
            metadata_uri=body.metadata_uri,
            content_hash=content_hash,
            supersedes=body.supersedes,
            relation=body.relation,
            within_envelope=body.within_envelope,
        )

        return {
            **result,
            "envelope_tx": envelope_tx,
            "line_name": body.line_name,
            "relation": body.relation,
            "within_envelope": body.within_envelope,
            "supersedes": body.supersedes,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("create-with-lineage failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
