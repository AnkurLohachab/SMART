"""Neo4j tracking utilities for the model card lifecycle."""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.db import neo4j_conn

logger = logging.getLogger(__name__)


async def track_model_card_in_neo4j(
    token_id: int,
    status: str,
    metadata: Dict[str, Any],
    address: str,
    action: str,
    additional_data: Optional[Dict[str, Any]] = None,
    creator_uuid: Optional[str] = None
):
    """Track model card creation and updates in Neo4j with the full schema."""

    model_details = metadata.get("1. Model Details", {})
    intended_use = metadata.get("2. Intended Use and Clinical Context", {})
    data_factors = metadata.get("3. Data & Factors", {})
    features_outputs = metadata.get("4. Features & Outputs", {})
    performance = metadata.get("5. Performance & Validation", {})
    methodology = metadata.get("6. Methodology & Explainability", {})
    additional_info = metadata.get("7. Additional Information", {})

    query = """
    MERGE (mc:ModelCard {token_id: $token_id})
    ON CREATE SET
        mc.created_at = datetime(),
        mc.blockchain_address = $address,
        mc.creator_uuid = coalesce($creator_uuid, mc.creator_uuid)
    SET
        mc.current_status = $status,
        mc.last_updated = datetime(),
        mc.last_updated_by = $address,

        // Section 1: Model Details
        mc.model_name = $model_name,
        mc.version = $version,
        mc.developer_organization = $developer_org,
        mc.release_date = $release_date,
        mc.description = $description,
        mc.intended_purpose = $intended_purpose,
        mc.algorithms_used = $algorithms_used,
        mc.gmdn_code = $gmdn_code,
        mc.licensing = $licensing,
        mc.support_contact = $support_contact,
        mc.literature_references = $literature_refs,
        mc.clinical_study_references = $clinical_refs,
        mc.logo_image = $logo_image,

        // Section 2: Intended Use and Clinical Context
        mc.primary_intended_users = $primary_users,
        mc.clinical_indications = $clinical_indications,
        mc.patient_target_group = $patient_target,
        mc.contraindications = $contraindications,
        mc.intended_use_environment = $use_environment,
        mc.out_of_scope_applications = $out_of_scope,
        mc.warnings = $warnings,

        // Section 3: Data & Factors (stored as JSON)
        mc.concept_sets = $concept_sets,
        mc.primary_cohort_criteria = $cohort_criteria,
        mc.source_datasets = $source_datasets,
        mc.data_distribution_summary = $data_distribution,
        mc.data_representativeness = $data_representativeness,
        mc.data_governance = $data_governance,

        // Section 4: Features & Outputs (stored as JSON)
        mc.input_features = $input_features,
        mc.output_features = $output_features,
        mc.feature_type_distribution = $feature_type_dist,
        mc.uncertainty_quantification = $uncertainty_quant,
        mc.output_interpretability = $output_interp,

        // Section 5: Performance & Validation (stored as JSON)
        mc.validation_datasets = $validation_datasets,
        mc.claimed_metrics = $claimed_metrics,
        mc.validated_metrics = $validated_metrics,
        mc.calibration_analysis = $calibration,
        mc.fairness_assessment = $fairness,
        mc.metric_validation_status = $metric_validation,

        // Section 6: Methodology & Explainability
        mc.model_development_workflow = $dev_workflow,
        mc.training_procedure = $training_proc,
        mc.data_preprocessing = $data_preprocessing,
        mc.synthetic_data_usage = $synthetic_data,
        mc.explainable_ai_method = $xai_method,
        mc.global_vs_local_interpretability = $interpretability,

        // Section 7: Additional Information
        mc.benefit_risk_summary = $benefit_risk,
        mc.post_market_surveillance_plan = $surveillance_plan,
        mc.ethical_considerations = $ethical_considerations,
        mc.caveats_and_limitations = $caveats_limitations,
        mc.recommendations_for_safe_use = $safe_use_recommendations,
        mc.explainability_recommendations = $explainability_recs,
        mc.supporting_documents = $supporting_docs,

        // Full metadata as JSON for backup
        mc.full_metadata = $full_metadata

    CREATE (event:StatusEvent {
        token_id: $token_id,
        status: $status,
        action: $action,
        timestamp: datetime(),
        actor: $address,
        event_metadata: $event_metadata
    })

    CREATE (mc)-[:HAS_EVENT]->(event)

    RETURN mc, event
    """

    try:
        params = {
            "token_id": token_id,
            "status": status,
            "address": address,
            "action": action,
            "creator_uuid": creator_uuid,
            "full_metadata": json.dumps(metadata),
            "event_metadata": json.dumps(additional_data or {}),

            "model_name": model_details.get("Model Name"),
            "version": model_details.get("Version"),
            "developer_org": model_details.get("Developer / Organization"),
            "release_date": model_details.get("Release Date"),
            "description": model_details.get("Description"),
            "intended_purpose": model_details.get("Intended Purpose"),
            "algorithms_used": model_details.get("Algorithm(s) Used"),
            "gmdn_code": model_details.get("GMDN Code"),
            "licensing": model_details.get("Licensing"),
            "support_contact": model_details.get("Support Contact"),
            "literature_refs": json.dumps(model_details.get("Literature References", [])),
            "clinical_refs": json.dumps(model_details.get("Clinical Study References", [])),
            "logo_image": model_details.get("Logo / Image (optional)"),

            "primary_users": intended_use.get("Primary Intended Users"),
            "clinical_indications": intended_use.get("Clinical Indications"),
            "patient_target": intended_use.get("Patient target group"),
            "contraindications": intended_use.get("Contraindications"),
            "use_environment": intended_use.get("Intended Use Environment"),
            "out_of_scope": intended_use.get("Out of Scope Applications"),
            "warnings": intended_use.get("Warnings"),

            "concept_sets": json.dumps(data_factors.get("Concept Sets", [])),
            "cohort_criteria": json.dumps(data_factors.get("Primary Cohort Criteria")),
            "source_datasets": json.dumps(data_factors.get("Source Datasets", [])),
            "data_distribution": data_factors.get("Data Distribution Summary"),
            "data_representativeness": data_factors.get("Data Representativeness"),
            "data_governance": data_factors.get("Data Governance"),

            "input_features": json.dumps(features_outputs.get("Input Features", [])),
            "output_features": json.dumps(features_outputs.get("Output Features", [])),
            "feature_type_dist": features_outputs.get("Feature Type Distribution"),
            "uncertainty_quant": features_outputs.get("Uncertainty Quantification"),
            "output_interp": features_outputs.get("Output Interpretability"),

            "validation_datasets": json.dumps(performance.get("Validation Dataset(s)", [])),
            "claimed_metrics": json.dumps(performance.get("Claimed Metrics", [])),
            "validated_metrics": json.dumps(performance.get("Validated Metrics", [])),
            "calibration": performance.get("Calibration Analysis"),
            "fairness": performance.get("Fairness Assessment"),
            "metric_validation": performance.get("Metric Validation Status"),

            "dev_workflow": methodology.get("Model Development Workflow"),
            "training_proc": methodology.get("Training Procedure"),
            "data_preprocessing": methodology.get("Data Preprocessing"),
            "synthetic_data": methodology.get("Synthetic Data Usage"),
            "xai_method": methodology.get("Explainable AI Method"),
            "interpretability": methodology.get("Global vs. Local Interpretability"),

            "benefit_risk": additional_info.get("Benefit–Risk Summary"),
            "surveillance_plan": additional_info.get("Post-Market Surveillance Plan"),
            "ethical_considerations": additional_info.get("Ethical Considerations"),
            "caveats_limitations": additional_info.get("Caveats & Limitations"),
            "safe_use_recommendations": additional_info.get("Recommendations for Safe Use"),
            "explainability_recs": additional_info.get("Explainability Recommendations"),
            "supporting_docs": json.dumps(additional_info.get("Supporting Documents", []))
        }

        await neo4j_conn.execute(query, params)
        logger.info(f"Tracked model card {token_id} in Neo4j - Status: {status}, Action: {action}")

        if creator_uuid:
            creator_query = """
            MATCH (u:User {uuid: $creator_uuid})
            MATCH (mc:ModelCard {token_id: $token_id})
            MERGE (u)-[:CREATED]->(mc)
            """
            try:
                await neo4j_conn.execute(creator_query, {
                    "creator_uuid": creator_uuid,
                    "token_id": token_id
                })
                logger.info(f"Created CREATED relationship for model card {token_id} with user {creator_uuid}")
            except Exception as rel_err:
                logger.warning(f"Could not create CREATED relationship: {rel_err}")

    except Exception as e:
        logger.error(f"Failed to track in Neo4j: {str(e)}")
        raise


async def update_model_card_status(
    token_id: int,
    status: str,
    address: str,
    action: str,
    event_metadata: Optional[Dict[str, Any]] = None
):
    """Update a model card's status without overwriting existing metadata."""
    query = """
    MATCH (mc:ModelCard {token_id: $token_id})
    SET
        mc.current_status = $status,
        mc.last_updated = datetime(),
        mc.last_updated_by = $address

    CREATE (event:StatusEvent {
        token_id: $token_id,
        status: $status,
        action: $action,
        timestamp: datetime(),
        actor: $address,
        event_metadata: $event_metadata
    })

    CREATE (mc)-[:HAS_EVENT]->(event)

    RETURN mc, event
    """

    try:
        params = {
            "token_id": token_id,
            "status": status,
            "address": address,
            "action": action,
            "event_metadata": json.dumps(event_metadata or {})
        }

        await neo4j_conn.execute(query, params)
        logger.info(f"Updated model card {token_id} status to {status} - Action: {action}")

    except Exception as e:
        logger.error(f"Failed to update status in Neo4j: {str(e)}")
        raise


async def get_model_card_history(token_id: int) -> Dict[str, Any]:
    """Get complete history of a model card including all status events."""
    query = """
    MATCH (mc:ModelCard {token_id: $token_id})
    OPTIONAL MATCH (mc)-[:HAS_EVENT]->(event:StatusEvent)
    RETURN mc, collect(event) as events
    ORDER BY event.timestamp DESC
    """

    try:
        result = await neo4j_conn.query(query, {"token_id": token_id})
        return result
    except Exception as e:
        logger.error(f"Failed to get model card history: {str(e)}")
        raise


async def get_all_model_cards(status: Optional[str] = None) -> list:
    """Get all model cards, optionally filtered by status."""
    if status:
        query = """
        MATCH (mc:ModelCard {current_status: $status})
        RETURN mc
        ORDER BY mc.created_at DESC
        """
        params = {"status": status}
    else:
        query = """
        MATCH (mc:ModelCard)
        RETURN mc
        ORDER BY mc.created_at DESC
        """
        params = {}

    try:
        result = await neo4j_conn.query(query, params)
        return result
    except Exception as e:
        logger.error(f"Failed to get model cards: {str(e)}")
        raise



async def create_or_update_model_lineage(
    organization: str,
    model_name: str,
    token_id: int
) -> Dict[str, Any]:
    """Create or update a ModelLineage node grouping all versions of a model."""
    lineage_id = f"{organization}_{model_name}".replace(" ", "_").lower()

    query = """
    MERGE (ml:ModelLineage {lineage_id: $lineage_id})
    ON CREATE SET
        ml.organization = $organization,
        ml.model_name = $model_name,
        ml.created_at = datetime()
    SET
        ml.last_updated = datetime()

    WITH ml
    MATCH (mc:ModelCard {token_id: $token_id})
    MERGE (mc)-[:BELONGS_TO_LINEAGE]->(ml)

    RETURN ml.lineage_id as lineage_id, ml.created_at as created_at
    """

    try:
        result = await neo4j_conn.query(query, {
            "lineage_id": lineage_id,
            "organization": organization,
            "model_name": model_name,
            "token_id": token_id
        })
        logger.info(f"Created/updated lineage {lineage_id} for token {token_id}")
        return {
            "lineage_id": lineage_id,
            "token_id": token_id,
            "result": result[0] if result else None
        }
    except Exception as e:
        logger.error(f"Failed to create/update model lineage: {str(e)}")
        raise


async def create_supersession_relationship(
    deprecated_token_id: int,
    successor_token_id: int,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """Create a SUPERSEDES relationship from a new version to its deprecated predecessor."""
    query = """
    MATCH (deprecated:ModelCard {token_id: $deprecated_token_id})
    MATCH (successor:ModelCard {token_id: $successor_token_id})

    // Create the SUPERSEDES relationship (successor supersedes deprecated)
    MERGE (successor)-[r:SUPERSEDES]->(deprecated)
    ON CREATE SET
        r.created_at = datetime(),
        r.reason = $reason

    // Update the model cards with cross-references
    SET deprecated.superseded_by = $successor_token_id,
        successor.supersedes = $deprecated_token_id

    RETURN deprecated.token_id as deprecated_id,
           deprecated.current_status as deprecated_status,
           successor.token_id as successor_id,
           successor.current_status as successor_status,
           r.created_at as relationship_created
    """

    try:
        result = await neo4j_conn.query(query, {
            "deprecated_token_id": deprecated_token_id,
            "successor_token_id": successor_token_id,
            "reason": reason or "Version upgrade"
        })

        if result:
            logger.info(f"Created supersession: {successor_token_id} supersedes {deprecated_token_id}")
            return {
                "success": True,
                "deprecated_token_id": deprecated_token_id,
                "successor_token_id": successor_token_id,
                "details": result[0]
            }
        else:
            return {
                "success": False,
                "message": "One or both model cards not found"
            }

    except Exception as e:
        logger.error(f"Failed to create supersession relationship: {str(e)}")
        raise


async def get_model_lineage(organization: str, model_name: str) -> Dict[str, Any]:
    """Get the complete version lineage for a model across all NFT IDs."""
    lineage_id = f"{organization}_{model_name}".replace(" ", "_").lower()

    query = """
    // Try to find by lineage first
    OPTIONAL MATCH (ml:ModelLineage {lineage_id: $lineage_id})
    OPTIONAL MATCH (mc_lineage:ModelCard)-[:BELONGS_TO_LINEAGE]->(ml)

    // Also find by org + name directly (for cards not yet linked to lineage)
    OPTIONAL MATCH (mc_direct:ModelCard)
    WHERE mc_direct.developer_organization = $organization
      AND mc_direct.model_name = $model_name

    // Combine results
    WITH collect(DISTINCT mc_lineage) + collect(DISTINCT mc_direct) as all_cards

    UNWIND all_cards as mc
    WITH DISTINCT mc
    WHERE mc IS NOT NULL

    OPTIONAL MATCH (mc)-[:SUPERSEDES]->(predecessor:ModelCard)
    OPTIONAL MATCH (successor:ModelCard)-[:SUPERSEDES]->(mc)

    RETURN mc.token_id as token_id,
           mc.version as version,
           mc.current_status as status,
           mc.created_at as created_at,
           mc.supersedes as supersedes_token_id,
           mc.superseded_by as superseded_by_token_id,
           predecessor.token_id as predecessor_id,
           successor.token_id as successor_id
    ORDER BY mc.created_at ASC
    """

    try:
        results = await neo4j_conn.query(query, {
            "lineage_id": lineage_id,
            "organization": organization,
            "model_name": model_name
        })

        active_version = None
        for r in results:
            if r.get("status") == "Published" and not r.get("superseded_by_token_id"):
                active_version = r
                break

        return {
            "lineage_id": lineage_id,
            "organization": organization,
            "model_name": model_name,
            "versions": results,
            "total_versions": len(results),
            "active_version": active_version
        }

    except Exception as e:
        logger.error(f"Failed to get model lineage: {str(e)}")
        raise


async def get_version_chain(token_id: int) -> Dict[str, Any]:
    """Get the predecessor/successor version chain for a specific model card."""
    query = """
    MATCH (mc:ModelCard {token_id: $token_id})

    // Get all predecessors (going back through SUPERSEDES or HAS_VERSION chain)
    OPTIONAL MATCH path_back = (mc)-[:SUPERSEDES|HAS_VERSION*1..10]->(predecessor:ModelCard)
    WITH mc, collect(DISTINCT predecessor) as predecessors

    // Get all successors (going forward - they point TO us via SUPERSEDES or from us via HAS_VERSION)
    OPTIONAL MATCH path_forward = (successor:ModelCard)-[:SUPERSEDES*1..10]->(mc)
    WITH mc, predecessors, collect(DISTINCT successor) as successors_supersede

    OPTIONAL MATCH (mc)-[:HAS_VERSION*1..10]->(successor2:ModelCard)
    WITH mc, predecessors, successors_supersede, collect(DISTINCT successor2) as successors_version

    // Combine successors
    WITH mc, predecessors, successors_supersede + successors_version as successors

    // Get immediate predecessor (parent via HAS_VERSION or superseded via SUPERSEDES)
    OPTIONAL MATCH (parent:ModelCard)-[:HAS_VERSION]->(mc)
    OPTIONAL MATCH (mc)-[:SUPERSEDES]->(superseded:ModelCard)
    WITH mc, predecessors, successors,
         COALESCE(parent, superseded) as immediate_predecessor

    // Get immediate successor (child via HAS_VERSION or superseding via SUPERSEDES)
    OPTIONAL MATCH (mc)-[:HAS_VERSION]->(child:ModelCard)
    OPTIONAL MATCH (superseding:ModelCard)-[:SUPERSEDES]->(mc)
    WITH mc, predecessors, successors, immediate_predecessor,
         COALESCE(child, superseding) as immediate_successor

    RETURN mc.token_id as token_id,
           mc.model_name as model_name,
           mc.version as version,
           mc.current_status as status,
           mc.developer_organization as organization,
           immediate_predecessor.token_id as immediate_predecessor_id,
           immediate_predecessor.version as predecessor_version,
           immediate_predecessor.current_status as predecessor_status,
           immediate_successor.token_id as immediate_successor_id,
           immediate_successor.version as successor_version,
           immediate_successor.current_status as successor_status,
           [p in predecessors | {token_id: p.token_id, version: p.version, status: p.current_status}] as all_predecessors,
           [s in successors | {token_id: s.token_id, version: s.version, status: s.current_status}] as all_successors
    """

    try:
        result = await neo4j_conn.query(query, {"token_id": token_id})

        if result:
            data = result[0]
            return {
                "token_id": token_id,
                "model_name": data.get("model_name"),
                "version": data.get("version"),
                "status": data.get("status"),
                "organization": data.get("organization"),
                "immediate_predecessor": {
                    "token_id": data.get("immediate_predecessor_id"),
                    "version": data.get("predecessor_version"),
                    "status": data.get("predecessor_status")
                } if data.get("immediate_predecessor_id") else None,
                "immediate_successor": {
                    "token_id": data.get("immediate_successor_id"),
                    "version": data.get("successor_version"),
                    "status": data.get("successor_status")
                } if data.get("immediate_successor_id") else None,
                "all_predecessors": data.get("all_predecessors", []),
                "all_successors": data.get("all_successors", [])
            }

        return {"token_id": token_id, "error": "Model card not found"}

    except Exception as e:
        logger.error(f"Failed to get version chain: {str(e)}")
        raise


async def find_deprecated_predecessor(
    organization: str,
    model_name: str
) -> Optional[Dict[str, Any]]:
    """Find the most recent deprecated model card for a given org + model name."""
    query = """
    MATCH (mc:ModelCard)
    WHERE mc.developer_organization = $organization
      AND mc.model_name = $model_name
      AND mc.current_status = 'Deprecated'
      AND NOT EXISTS { MATCH ()-[:SUPERSEDES]->(mc) }
    RETURN mc.token_id as token_id,
           mc.version as version,
           mc.current_status as status,
           mc.created_at as created_at
    ORDER BY mc.created_at DESC
    LIMIT 1
    """

    try:
        result = await neo4j_conn.query(query, {
            "organization": organization,
            "model_name": model_name
        })

        if result and result[0].get("token_id"):
            return result[0]
        return None

    except Exception as e:
        logger.error(f"Failed to find deprecated predecessor: {str(e)}")
        raise


async def find_latest_version(
    organization: str,
    model_name: str
) -> Optional[Dict[str, Any]]:
    """Find the latest model card for a given org + model name, regardless of status."""
    query = """
    MATCH (mc:ModelCard)
    WHERE mc.developer_organization = $organization
      AND mc.model_name = $model_name
    RETURN mc.token_id as token_id,
           mc.version as version,
           mc.current_status as status,
           mc.created_at as created_at
    ORDER BY mc.created_at DESC
    LIMIT 1
    """

    try:
        result = await neo4j_conn.query(query, {
            "organization": organization,
            "model_name": model_name
        })

        if result and result[0].get("token_id"):
            return result[0]
        return None

    except Exception as e:
        logger.error(f"Failed to find latest version: {str(e)}")
        raise
