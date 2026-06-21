"""Model card API routes backed by the smart-model-card package."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import date, datetime
import json
import tempfile
import os
import logging

from app.utils.minio_utils import upload_to_minio
from app.utils.blockchain import (
    create_model_card_on_chain,
    create_model_card_with_lineage_on_chain,
    pin_line_envelope_on_chain,
)
from web3 import Web3 as _W3
from app.utils.neo4j_tracking import (
    track_model_card_in_neo4j,
    create_or_update_model_lineage,
    create_supersession_relationship,
    find_latest_version,
    find_deprecated_predecessor
)
from app.db import neo4j_conn

logger = logging.getLogger(__name__)


def _clean_create_error(exc: Exception) -> str:
    """Translate a web3/contract revert into a short user-facing message."""
    msg = str(exc)

    if "Name owned by other controller" in msg:
        return (
            "A model card with this name already exists. "
            "Use 'New version' to extend the existing line instead of creating a duplicate."
        )
    if "Envelope pinned by different controller" in msg:
        return (
            "This model name is already in use by another developer "
            "(an envelope is pinned to it on chain). Please choose a different name."
        )
    if "Token already named" in msg:
        return "This token has already been registered under a name."
    if "Name required" in msg:
        return "Model name is required."
    if "Controller required" in msg:
        return "Creator address is missing or invalid."
    if "Invalid alias length" in msg:
        return "Internal: invalid name alias length."
    if "Envelope already pinned" in msg:
        return "An envelope is already pinned for this line. You don't need to pin it again."

    short = msg.splitlines()[0].strip()
    for prefix in ("execution reverted: ", "Execution reverted: ", "VM Exception while processing transaction: reverted with reason string '"):
        if short.startswith(prefix):
            short = short[len(prefix):].rstrip("'\"")
            break
    if len(short) > 240:
        short = short[:237] + "…"
    return short or "Failed to create model card."


def _slugify(name: str) -> str:
    """Slugify: lowercase, spaces to dashes, drop everything else."""
    import re
    s = (name or "").strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


async def _auto_derive_lineage(
    model_name: str,
    creator_address: str,
    override: Optional["LineageBlock"] = None,
    *,
    is_root_only: bool = False,
) -> Dict[str, Any]:
    """Read on-chain line state and return a populated lineage block; override fields win."""
    slug = _slugify(model_name)
    if not slug:
        return {
            "line_name": None,
            "supersedes": 0,
            "relation": 0,
            "within_envelope": False,
            "envelope_text": None,
            "auto": True,
            "is_root": True,
        }

    from app.utils.lineage import get_line as _get_line
    try:
        state = _get_line(slug)
    except Exception:
        state = None

    versions = (state or {}).get("versions") or []
    has_record = bool((state or {}).get("has_name_record"))
    controller = ((state or {}).get("controller") or "").lower()
    creator_lc = (creator_address or "").lower()

    if has_record and controller and creator_lc and controller != creator_lc:
        from app.db import neo4j_conn
        same_user = False
        try:
            controller_uuid = await neo4j_conn.get_uuid_for_address(controller)
            creator_uuid = await neo4j_conn.get_uuid_for_address(creator_lc)
            if controller_uuid and creator_uuid and controller_uuid == creator_uuid:
                same_user = True
        except Exception:
            pass
        if not same_user:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This model name is already in use by another developer. "
                    "Please choose a different name."
                ),
            )

    if is_root_only and has_record and len(versions) > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "You already have a model card with this name. "
                "Switch to 'New Version' mode to add another version, or pick a different name."
            ),
        )

    is_root = not has_record or len(versions) == 0
    supersedes = 0 if is_root else int(versions[-1]["token_id"])
    envelope_pinned = bool(((state or {}).get("envelope") or {}).get("pinned_at"))

    derived = {
        "line_name": slug,
        "supersedes": supersedes,
        "relation": 0,
        "within_envelope": (not is_root) and envelope_pinned,
        "envelope_text": None,
        "auto": True,
        "is_root": is_root,
        "next_version_index": len(versions) + 1,
        "envelope_pinned": envelope_pinned,
    }

    if override is not None:
        if override.line_name:
            derived["line_name"] = _slugify(override.line_name)
        if override.relation is not None:
            derived["relation"] = int(override.relation)
        if override.supersedes is not None:
            derived["supersedes"] = int(override.supersedes)
        if override.within_envelope is not None:
            derived["within_envelope"] = bool(override.within_envelope)
        if override.envelope_text:
            derived["envelope_text"] = override.envelope_text
        derived["auto"] = False

    return derived


def _http_status_for(exc: Exception) -> int:
    msg = str(exc)
    if (
        "Name owned by other controller" in msg
        or "Envelope pinned by different controller" in msg
        or "Envelope already pinned" in msg
        or "Token already named" in msg
    ):
        return 409
    if "Name required" in msg or "Controller required" in msg:
        return 400
    return 500

try:
    from smart_model_card import (
        ModelCard,
        ModelDetails,
        IntendedUse,
        DataFactors,
        FeaturesOutputs,
        PerformanceValidation,
        Methodology,
        AdditionalInfo,
        HTMLExporter,
        JSONExporter
    )
    from smart_model_card.sections import (
        SourceDataset,
        InputFeature,
        OutputFeature,
        ValidationDataset,
        PerformanceMetric,
        ConceptSet,
        CohortCriteria
    )
    SMART_MODEL_CARD_AVAILABLE = True
except ImportError:
    SMART_MODEL_CARD_AVAILABLE = False

router = APIRouter()


class ModelDetailsRequest(BaseModel):
    model_name: str
    version: str = "1.0.0"
    developer_organization: str
    release_date: str = "2025-01-01"
    description: str
    clinical_function: str = "decision_support"
    intended_purpose: str
    algorithms_used: str
    licensing: str = "Not specified"
    gmdn_code: Optional[str] = None
    support_contact: str
    literature_references: Optional[List[str]] = None
    information_significance: Optional[str] = None
    basic_udi_di: Optional[str] = None
    udi_di: Optional[str] = None
    regulatory_classifications: Optional[List[Dict[str, str]]] = None
    clinical_study_references: Optional[List[str]] = None
    logo_image: Optional[str] = None


class IntendedUseRequest(BaseModel):
    primary_intended_users: str
    clinical_indications: str
    patient_target_group: str
    intended_use_environment: str
    contraindications: Optional[str] = None
    out_of_scope_applications: Optional[str] = None
    warnings: Optional[str] = None


class SourceDatasetRequest(BaseModel):
    name: str
    origin: str
    size: int
    collection_period: str
    population_characteristics: str
    demographics: Optional[Dict[str, str]] = None


class ConceptSetRequest(BaseModel):
    name: str
    vocabulary: str
    concept_ids: List[int]
    description: Optional[str] = None


class CohortCriteriaRequest(BaseModel):
    inclusion_rules: List[str]
    exclusion_rules: Optional[List[str]] = None
    observation_window: Optional[str] = None


class DataFactorsRequest(BaseModel):
    source_datasets: List[SourceDatasetRequest]
    concept_sets: Optional[List[ConceptSetRequest]] = None
    primary_cohort_criteria: Optional[CohortCriteriaRequest] = None
    data_distribution_summary: Any
    data_representativeness: str
    data_governance: str
    deid_method: Optional[str] = None
    date_handling: Optional[str] = None


class InputFeatureRequest(BaseModel):
    name: str
    data_type: str
    required: bool = True
    clinical_domain: Optional[str] = None
    value_range: Optional[str] = None
    units: Optional[str] = None


class OutputFeatureRequest(BaseModel):
    name: str
    type: str
    value_range: Optional[str] = None
    units: Optional[str] = None
    classes: Optional[List[str]] = None


class FeaturesOutputsRequest(BaseModel):
    input_features: Any
    output_features: Any
    feature_type_distribution: str = "Not specified"
    uncertainty_quantification: str = "Not specified"
    output_interpretability: str = "Not specified"


class ValidationDatasetRequest(BaseModel):
    name: str
    source_institution: str
    population_characteristics: str
    validation_type: str


class PerformanceMetricRequest(BaseModel):
    name: str
    value: float
    status: str
    subgroup: Optional[str] = None


class PerformanceValidationRequest(BaseModel):
    validation_datasets: Any
    claimed_metrics: Any
    validated_metrics: Any = "Pending validation"
    calibration_analysis: Optional[str] = None
    fairness_assessment: Optional[str] = None
    metric_validation_status: Optional[str] = None


class MethodologyRequest(BaseModel):
    model_development_workflow: str
    training_procedure: str
    data_preprocessing: str
    synthetic_data_usage: Optional[str] = None
    explainable_ai_method: Optional[str] = None
    global_vs_local_interpretability: Optional[str] = None


class AdditionalInfoRequest(BaseModel):
    benefit_risk_summary: str
    ethical_considerations: str = "Not specified"
    caveats_limitations: str
    recommendations_for_safe_use: str
    post_market_surveillance_plan: Optional[str] = None
    explainability_recommendations: Optional[str] = None
    supporting_documents: Optional[List[str]] = None


class LineageBlock(BaseModel):
    """Optional overrides for the auto-derived lineage block."""
    line_name: Optional[str] = None
    relation: Optional[int] = None
    supersedes: Optional[int] = None
    within_envelope: Optional[bool] = None
    envelope_text: Optional[str] = None


class CreateModelCardRequest(BaseModel):
    developer_address: str
    creator_uuid: Optional[str] = None
    model_details: ModelDetailsRequest
    intended_use: IntendedUseRequest
    data_factors: DataFactorsRequest
    features_outputs: FeaturesOutputsRequest
    performance_validation: PerformanceValidationRequest
    methodology: MethodologyRequest
    additional_info: AdditionalInfoRequest
    lineage: Optional[LineageBlock] = None



def build_source_datasets(datasets: List[SourceDatasetRequest]) -> List[SourceDataset]:
    """Convert API request datasets to smart-model-card SourceDataset objects"""
    return [
        SourceDataset(
            name=ds.name,
            origin=ds.origin,
            size=ds.size,
            collection_period=ds.collection_period,
            population_characteristics=ds.population_characteristics,
            demographics=ds.demographics
        )
        for ds in datasets
    ]


def build_concept_sets(concept_sets: Optional[List[ConceptSetRequest]]) -> Optional[List[ConceptSet]]:
    """Convert API request concept sets to smart-model-card ConceptSet objects"""
    if not concept_sets:
        return None
    return [
        ConceptSet(
            name=cs.name,
            vocabulary=cs.vocabulary,
            concept_ids=cs.concept_ids,
            description=cs.description
        )
        for cs in concept_sets
    ]


def build_cohort_criteria(criteria: Optional[CohortCriteriaRequest]) -> Optional[CohortCriteria]:
    """Convert API request cohort criteria to smart-model-card CohortCriteria object"""
    if not criteria:
        return None
    return CohortCriteria(
        inclusion_rules=criteria.inclusion_rules,
        exclusion_rules=criteria.exclusion_rules,
        observation_window=criteria.observation_window
    )


def build_input_features(features: Any) -> List:
    """Convert input features - can be string or list of InputFeature objects"""
    if isinstance(features, str):
        feature_names = [f.strip() for f in features.split(',')]
        return [
            InputFeature(
                name=name,
                data_type="other",
                required=True,
                clinical_domain="General"
            )
            for name in feature_names
        ]
    if isinstance(features, list):
        result = []
        for f in features:
            if isinstance(f, dict):
                result.append(InputFeature(
                    name=f.get('name'),
                    data_type=f.get('data_type', 'other'),
                    required=f.get('required', True),
                    clinical_domain=f.get('clinical_domain', 'General'),
                    value_range=f.get('value_range'),
                    units=f.get('units')
                ))
            else:
                result.append(f)
        return result
    return features


def build_output_features(features: Any) -> List:
    """Convert output features - can be string or list of OutputFeature objects"""
    if isinstance(features, str):
        feature_names = [f.strip() for f in features.split(',')]
        return [
            OutputFeature(
                name=name,
                type="other"
            )
            for name in feature_names
        ]
    if isinstance(features, list):
        result = []
        for f in features:
            if isinstance(f, dict):
                result.append(OutputFeature(
                    name=f.get('name'),
                    type=f.get('type', 'other'),
                    value_range=f.get('value_range'),
                    units=f.get('units'),
                    classes=f.get('classes')
                ))
            else:
                result.append(f)
        return result
    return features


def build_validation_datasets(datasets: Any) -> List:
    """Convert validation datasets - can be string or list"""
    if isinstance(datasets, str):
        return [
            ValidationDataset(
                name="Validation Dataset",
                source_institution="External",
                population_characteristics=datasets,
                validation_type="holdout"
            )
        ]
    if isinstance(datasets, list):
        result = []
        for ds in datasets:
            if isinstance(ds, dict):
                result.append(ValidationDataset(
                    name=ds.get('name', 'Validation Dataset'),
                    source_institution=ds.get('source_institution', 'External'),
                    population_characteristics=ds.get('population_characteristics', 'Not specified'),
                    validation_type=ds.get('validation_type', 'holdout')
                ))
            else:
                result.append(ds)
        return result
    return datasets


def build_metrics(metrics: Any) -> List:
    """Convert metrics - can be string or list of PerformanceMetric objects"""
    import re
    if isinstance(metrics, str):
        result = []
        for part in metrics.split(','):
            part = part.strip()
            if ':' in part:
                name, value_str = part.split(':', 1)
                value_str = value_str.strip()
                numeric_match = re.match(r'^([\d.]+)', value_str)
                if numeric_match:
                    try:
                        value = float(numeric_match.group(1))
                    except ValueError:
                        value = 0.0
                else:
                    value = 0.0
                result.append(PerformanceMetric(
                    metric_name=name.strip(),
                    value=value,
                    validation_status="Claimed"
                ))
            else:
                result.append(PerformanceMetric(
                    metric_name=part,
                    value=0.0,
                    validation_status="Claimed"
                ))
        return result if result else [PerformanceMetric(metric_name="Not specified", value=0.0, validation_status="Pending")]
    if isinstance(metrics, list):
        result = []
        for m in metrics:
            if isinstance(m, dict):
                result.append(PerformanceMetric(
                    metric_name=m.get('name') or m.get('metric_name', 'Metric'),
                    value=m.get('value', 0.0),
                    validation_status=m.get('status') or m.get('validation_status', 'Claimed'),
                    subgroup=m.get('subgroup')
                ))
            else:
                result.append(m)
        return result
    return metrics



@router.post("/api/smart-model-card/create")
async def create_smart_model_card(request: CreateModelCardRequest):
    """Create a model card using the smart-model-card package (full 7-section schema)."""
    if not SMART_MODEL_CARD_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="smart-model-card package not installed. Install with: pip install smart-model-card"
        )

    try:
        card = ModelCard()

        card.set_model_details(ModelDetails(
            model_name=request.model_details.model_name,
            version=request.model_details.version,
            developer_organization=request.model_details.developer_organization,
            release_date=request.model_details.release_date,
            description=request.model_details.description,
            clinical_function=request.model_details.clinical_function,
            intended_purpose=request.model_details.intended_purpose,
            algorithms_used=request.model_details.algorithms_used,
            licensing=request.model_details.licensing,
            gmdn_code=request.model_details.gmdn_code,
            support_contact=request.model_details.support_contact,
            literature_references=request.model_details.literature_references,
            information_significance=request.model_details.information_significance,
            basic_udi_di=request.model_details.basic_udi_di,
            udi_di=request.model_details.udi_di,
            regulatory_classifications=request.model_details.regulatory_classifications,
            clinical_study_references=request.model_details.clinical_study_references,
            logo_image=request.model_details.logo_image,
        ))

        card.set_intended_use(IntendedUse(
            primary_intended_users=request.intended_use.primary_intended_users,
            clinical_indications=request.intended_use.clinical_indications,
            patient_target_group=request.intended_use.patient_target_group,
            intended_use_environment=request.intended_use.intended_use_environment,
            contraindications=request.intended_use.contraindications,
            out_of_scope_applications=request.intended_use.out_of_scope_applications,
            warnings=request.intended_use.warnings
        ))

        data_factors_kwargs = {
            'source_datasets': build_source_datasets(request.data_factors.source_datasets),
            'data_distribution_summary': request.data_factors.data_distribution_summary,
            'data_representativeness': request.data_factors.data_representativeness,
            'data_governance': request.data_factors.data_governance
        }

        if request.data_factors.concept_sets:
            data_factors_kwargs['concept_sets'] = build_concept_sets(request.data_factors.concept_sets)
        if request.data_factors.primary_cohort_criteria:
            data_factors_kwargs['primary_cohort_criteria'] = build_cohort_criteria(request.data_factors.primary_cohort_criteria)
        if request.data_factors.deid_method:
            data_factors_kwargs['deid_method'] = request.data_factors.deid_method
        if request.data_factors.date_handling:
            data_factors_kwargs['date_handling'] = request.data_factors.date_handling

        card.set_data_factors(DataFactors(**data_factors_kwargs))

        card.set_features_outputs(FeaturesOutputs(
            input_features=build_input_features(request.features_outputs.input_features),
            output_features=build_output_features(request.features_outputs.output_features),
            feature_type_distribution=request.features_outputs.feature_type_distribution,
            uncertainty_quantification=request.features_outputs.uncertainty_quantification,
            output_interpretability=request.features_outputs.output_interpretability
        ))

        perf_kwargs = {
            'validation_datasets': build_validation_datasets(request.performance_validation.validation_datasets),
            'claimed_metrics': build_metrics(request.performance_validation.claimed_metrics),
            'validated_metrics': build_metrics(request.performance_validation.validated_metrics)
        }
        if request.performance_validation.calibration_analysis:
            perf_kwargs['calibration_analysis'] = request.performance_validation.calibration_analysis
        if request.performance_validation.fairness_assessment:
            perf_kwargs['fairness_assessment'] = request.performance_validation.fairness_assessment
        if request.performance_validation.metric_validation_status:
            perf_kwargs['metric_validation_status'] = request.performance_validation.metric_validation_status

        card.set_performance_validation(PerformanceValidation(**perf_kwargs))

        method_kwargs = {
            'model_development_workflow': request.methodology.model_development_workflow,
            'training_procedure': request.methodology.training_procedure,
            'data_preprocessing': request.methodology.data_preprocessing
        }
        if request.methodology.synthetic_data_usage:
            method_kwargs['synthetic_data_usage'] = request.methodology.synthetic_data_usage
        if request.methodology.explainable_ai_method:
            method_kwargs['explainable_ai_method'] = request.methodology.explainable_ai_method
        if request.methodology.global_vs_local_interpretability:
            method_kwargs['global_vs_local_interpretability'] = request.methodology.global_vs_local_interpretability

        card.set_methodology(Methodology(**method_kwargs))

        additional_kwargs = {
            'benefit_risk_summary': request.additional_info.benefit_risk_summary,
            'ethical_considerations': request.additional_info.ethical_considerations,
            'caveats_limitations': request.additional_info.caveats_limitations,
            'recommendations_for_safe_use': request.additional_info.recommendations_for_safe_use
        }
        if request.additional_info.post_market_surveillance_plan:
            additional_kwargs['post_market_surveillance_plan'] = request.additional_info.post_market_surveillance_plan
        if request.additional_info.explainability_recommendations:
            additional_kwargs['explainability_recommendations'] = request.additional_info.explainability_recommendations
        if request.additional_info.supporting_documents:
            additional_kwargs['supporting_documents'] = request.additional_info.supporting_documents

        card.set_additional_info(AdditionalInfo(**additional_kwargs))

        standardized_metadata = card.to_dict()

        try:
            from jsonschema import validate as _js_validate, ValidationError as _JSValErr
            from smart_model_card import get_model_card_json_schema
            _js_validate(instance=standardized_metadata, schema=get_model_card_json_schema())
        except _JSValErr as exc:
            field_path = ".".join(str(p) for p in exc.absolute_path) or "(root)"
            raise HTTPException(
                status_code=422,
                detail=f"Schema validation failed at {field_path}: {exc.message}",
            )

        logger.info(f"Model card validated and standardized for: {request.model_details.model_name}")

        model_name = request.model_details.model_name
        version = request.model_details.version
        metadata_json = json.dumps(standardized_metadata, indent=2, sort_keys=True, default=str)
        file_key = f"model-cards/{model_name}_{version}_{datetime.utcnow().timestamp()}.json"

        metadata_uri = await upload_to_minio(
            file_key,
            metadata_json.encode('utf-8'),
            content_type="application/json"
        )
        logger.info(f"Metadata uploaded to MinIO: {metadata_uri}")

        envelope_tx = None
        derived_ln = await _auto_derive_lineage(
            request.model_details.model_name,
            request.developer_address,
            is_root_only=True,
            override=request.lineage,
        )
        if derived_ln.get("line_name"):
            from hashlib import sha256
            content_hash_bytes = sha256(metadata_json.encode("utf-8")).digest()

            class _Ln:
                pass
            ln = _Ln()
            ln.line_name = derived_ln["line_name"]
            ln.supersedes = derived_ln["supersedes"]
            ln.relation = derived_ln["relation"]
            ln.within_envelope = derived_ln["within_envelope"]
            ln.envelope_text = derived_ln["envelope_text"]

            if ln.envelope_text and ln.supersedes == 0:
                from app.utils.lineage import get_line as _get_line
                try:
                    line_state = _get_line(ln.line_name)
                except Exception:
                    line_state = None

                env = (line_state or {}).get("envelope") or {}
                pinned_at = int(env.get("pinned_at") or 0)
                pinned_by = (env.get("pinned_by") or "").lower()
                creator_lc = (request.developer_address or "").lower()

                if pinned_at == 0:
                    envelope_hash = _W3.keccak(text=ln.envelope_text)
                    envelope_tx = await pin_line_envelope_on_chain(
                        ln.line_name, envelope_hash, request.developer_address
                    )
                    logger.info(f"Envelope pinned for line '{ln.line_name}': tx={envelope_tx.get('tx_hash')}")
                elif pinned_by and pinned_by != creator_lc:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "This model name is already in use by another developer "
                            "(an envelope is pinned to it on chain). Please choose a different name."
                        ),
                    )
                else:
                    logger.info(
                        f"Envelope already pinned for line '{ln.line_name}' by this controller - skipping pin"
                    )

            tx_result = await create_model_card_with_lineage_on_chain(
                creator=request.developer_address,
                name=ln.line_name,
                metadata_uri=metadata_uri,
                content_hash=content_hash_bytes,
                supersedes=ln.supersedes,
                relation=ln.relation,
                within_envelope=ln.within_envelope,
            )
            token_id = tx_result["token_id"]
            if not token_id:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "On-chain mint did not emit the expected event. "
                        "The transaction may have reverted. No model card "
                        "was created. Check backend logs for the tx hash "
                        f"({tx_result.get('tx_hash')}) and retry."
                    ),
                )
            content_hash = "0x" + content_hash_bytes.hex()
            logger.info(f"NFT minted with lineage. token={token_id} line={ln.line_name} relation={ln.relation}")
        else:
            tx_result = await create_model_card_on_chain(
                creator=request.developer_address,
                metadata_uri=metadata_uri,
                metadata_json=metadata_json
            )
            token_id = tx_result["token_id"]
            if not token_id:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "On-chain mint did not emit the expected event. "
                        "The transaction may have reverted. No model card "
                        "was created."
                    ),
                )
            content_hash = tx_result.get("content_hash")
            logger.info(f"NFT minted (legacy path). token_id={token_id} hash={content_hash}")

        await track_model_card_in_neo4j(
            token_id=token_id,
            status="Created",
            metadata=standardized_metadata,
            address=request.developer_address,
            action="NFTMinted",
            additional_data={
                "tx_hash": tx_result.get("tx_hash"),
                "metadata_uri": metadata_uri,
            },
            creator_uuid=request.creator_uuid
        )
        logger.info(f"Model card tracked in Neo4j with token ID: {token_id}")

        html_content = None
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                html_path = os.path.join(tmpdir, "model_card.html")
                HTMLExporter.export(card, html_path)
                with open(html_path, 'r') as f:
                    html_content = f.read()
        except Exception as html_error:
            logger.warning(f"Could not generate HTML preview: {html_error}")

        return {
            "success": True,
            "message": f"Model card created and minted as NFT #{token_id}",
            "token_id": token_id,
            "metadata_uri": metadata_uri,
            "content_hash": content_hash,
            "tx_hash": tx_result.get("tx_hash"),
            "status": "Created",
            "blockchain_info": {
                "network": "hardhat",
                "contract": "MLUCE",
                "integrity_verification": "SHA-256 hash of metadata stored on-chain",
                "verification_endpoint": f"/api/model-cards/{token_id}/verify"
            },
            "model_card": standardized_metadata,
            "html_preview": html_content[:1000] + "..." if html_content and len(html_content) > 1000 else html_content,
            "model_name": request.model_details.model_name,
            "version": request.model_details.version,
            "developer": request.model_details.developer_organization
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create model card")
        raise HTTPException(
            status_code=_http_status_for(e),
            detail=_clean_create_error(e),
        )


@router.get("/api/smart-model-card/lineage-preview")
async def lineage_preview(
    model_name: str,
    creator: str,
    mode: str = "new",
):
    """Auto-derived lineage preview for the create form."""
    try:
        derived = await _auto_derive_lineage(
            model_name, creator, override=None,
            is_root_only=(mode == "new"),
        )
    except HTTPException as he:
        return {"ok": False, "status": he.status_code, "detail": he.detail}
    except Exception as e:
        return {"ok": False, "status": 500, "detail": _clean_create_error(e)}
    return {"ok": True, **derived}


@router.get("/api/smart-model-card/check")
async def check_package():
    """Check if smart-model-card package is available"""
    version = None
    if SMART_MODEL_CARD_AVAILABLE:
        try:
            import smart_model_card
            version = getattr(smart_model_card, '__version__', 'unknown')
        except:
            pass

    return {
        "available": SMART_MODEL_CARD_AVAILABLE,
        "version": version,
        "message": f"smart-model-card package v{version} is installed" if SMART_MODEL_CARD_AVAILABLE
                   else "smart-model-card package not found. Install with: pip install smart-model-card"
    }


@router.get("/api/smart-model-card/schema")
async def get_schema():
    """Return the expected schema for model card creation"""
    return {
        "sections": [
            {
                "number": 1,
                "name": "Model Details",
                "required_fields": ["model_name", "version", "developer_organization", "description", "intended_purpose", "algorithms_used", "support_contact"],
                "optional_fields": ["release_date", "licensing", "gmdn_code", "literature_references"]
            },
            {
                "number": 2,
                "name": "Intended Use",
                "required_fields": ["primary_intended_users", "clinical_indications", "patient_target_group", "intended_use_environment"],
                "optional_fields": ["contraindications", "out_of_scope_applications", "warnings"]
            },
            {
                "number": 3,
                "name": "Data & Factors",
                "required_fields": ["source_datasets", "data_distribution_summary", "data_representativeness", "data_governance"],
                "optional_fields": ["concept_sets", "primary_cohort_criteria", "deid_method", "date_handling"],
                "note": "Supports OMOP CDM integration via concept_sets and cohort_criteria"
            },
            {
                "number": 4,
                "name": "Features & Outputs",
                "required_fields": ["input_features", "output_features"],
                "optional_fields": ["feature_type_distribution", "uncertainty_quantification", "output_interpretability"]
            },
            {
                "number": 5,
                "name": "Performance & Validation",
                "required_fields": ["validation_datasets", "claimed_metrics"],
                "optional_fields": ["validated_metrics", "calibration_analysis", "fairness_assessment", "metric_validation_status"]
            },
            {
                "number": 6,
                "name": "Methodology",
                "required_fields": ["model_development_workflow", "training_procedure", "data_preprocessing"],
                "optional_fields": ["synthetic_data_usage", "explainable_ai_method", "global_vs_local_interpretability"]
            },
            {
                "number": 7,
                "name": "Additional Information",
                "required_fields": ["benefit_risk_summary", "caveats_limitations", "recommendations_for_safe_use"],
                "optional_fields": ["ethical_considerations", "post_market_surveillance_plan", "explainability_recommendations", "supporting_documents"]
            }
        ],
        "intended_purpose_options": ["decision_support", "screening", "diagnosis", "prognosis", "other"],
        "intended_use_environment_options": ["hospital_inpatient", "hospital_outpatient", "clinic", "home", "mobile", "other"]
    }


@router.post("/api/smart-model-card/create-version")
async def create_smart_model_card_version(request: CreateModelCardRequest):
    """Create a new version of an existing model card, linked to its parent."""
    if not SMART_MODEL_CARD_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="smart-model-card package not installed"
        )

    try:
        model_name = request.model_details.model_name
        developer_org = request.model_details.developer_organization

        if not model_name:
            raise HTTPException(status_code=400, detail="Model Name is required")
        if not developer_org:
            raise HTTPException(status_code=400, detail="Developer / Organization is required")

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

        request.model_details.version = new_version

        card = ModelCard()

        card.set_model_details(ModelDetails(
            model_name=model_name,
            version=new_version,
            developer_organization=developer_org,
            release_date=request.model_details.release_date,
            description=request.model_details.description,
            clinical_function=request.model_details.clinical_function,
            intended_purpose=request.model_details.intended_purpose,
            algorithms_used=request.model_details.algorithms_used,
            licensing=request.model_details.licensing,
            gmdn_code=request.model_details.gmdn_code,
            support_contact=request.model_details.support_contact,
            literature_references=request.model_details.literature_references
        ))

        card.set_intended_use(IntendedUse(
            primary_intended_users=request.intended_use.primary_intended_users,
            clinical_indications=request.intended_use.clinical_indications,
            patient_target_group=request.intended_use.patient_target_group,
            intended_use_environment=request.intended_use.intended_use_environment,
            contraindications=request.intended_use.contraindications,
            out_of_scope_applications=request.intended_use.out_of_scope_applications,
            warnings=request.intended_use.warnings
        ))

        data_factors_kwargs = {
            'source_datasets': build_source_datasets(request.data_factors.source_datasets),
            'data_distribution_summary': request.data_factors.data_distribution_summary,
            'data_representativeness': request.data_factors.data_representativeness,
            'data_governance': request.data_factors.data_governance
        }
        if request.data_factors.concept_sets:
            data_factors_kwargs['concept_sets'] = build_concept_sets(request.data_factors.concept_sets)
        if request.data_factors.primary_cohort_criteria:
            data_factors_kwargs['primary_cohort_criteria'] = build_cohort_criteria(request.data_factors.primary_cohort_criteria)
        if request.data_factors.deid_method:
            data_factors_kwargs['deid_method'] = request.data_factors.deid_method
        if request.data_factors.date_handling:
            data_factors_kwargs['date_handling'] = request.data_factors.date_handling
        card.set_data_factors(DataFactors(**data_factors_kwargs))

        card.set_features_outputs(FeaturesOutputs(
            input_features=build_input_features(request.features_outputs.input_features),
            output_features=build_output_features(request.features_outputs.output_features),
            feature_type_distribution=request.features_outputs.feature_type_distribution,
            uncertainty_quantification=request.features_outputs.uncertainty_quantification,
            output_interpretability=request.features_outputs.output_interpretability
        ))

        perf_kwargs = {
            'validation_datasets': build_validation_datasets(request.performance_validation.validation_datasets),
            'claimed_metrics': build_metrics(request.performance_validation.claimed_metrics),
            'validated_metrics': build_metrics(request.performance_validation.validated_metrics)
        }
        if request.performance_validation.calibration_analysis:
            perf_kwargs['calibration_analysis'] = request.performance_validation.calibration_analysis
        if request.performance_validation.fairness_assessment:
            perf_kwargs['fairness_assessment'] = request.performance_validation.fairness_assessment
        if request.performance_validation.metric_validation_status:
            perf_kwargs['metric_validation_status'] = request.performance_validation.metric_validation_status
        card.set_performance_validation(PerformanceValidation(**perf_kwargs))

        method_kwargs = {
            'model_development_workflow': request.methodology.model_development_workflow,
            'training_procedure': request.methodology.training_procedure,
            'data_preprocessing': request.methodology.data_preprocessing
        }
        if request.methodology.synthetic_data_usage:
            method_kwargs['synthetic_data_usage'] = request.methodology.synthetic_data_usage
        if request.methodology.explainable_ai_method:
            method_kwargs['explainable_ai_method'] = request.methodology.explainable_ai_method
        if request.methodology.global_vs_local_interpretability:
            method_kwargs['global_vs_local_interpretability'] = request.methodology.global_vs_local_interpretability
        card.set_methodology(Methodology(**method_kwargs))

        additional_kwargs = {
            'benefit_risk_summary': request.additional_info.benefit_risk_summary,
            'ethical_considerations': request.additional_info.ethical_considerations,
            'caveats_limitations': request.additional_info.caveats_limitations,
            'recommendations_for_safe_use': request.additional_info.recommendations_for_safe_use
        }
        if request.additional_info.post_market_surveillance_plan:
            additional_kwargs['post_market_surveillance_plan'] = request.additional_info.post_market_surveillance_plan
        if request.additional_info.explainability_recommendations:
            additional_kwargs['explainability_recommendations'] = request.additional_info.explainability_recommendations
        if request.additional_info.supporting_documents:
            additional_kwargs['supporting_documents'] = request.additional_info.supporting_documents
        card.set_additional_info(AdditionalInfo(**additional_kwargs))

        standardized_metadata = card.to_dict()

        if parent_token_id:
            standardized_metadata["parent_token_id"] = parent_token_id
            standardized_metadata["parent_version"] = current_version
        if deprecated_predecessor:
            standardized_metadata["supersedes_deprecated"] = deprecated_predecessor.get("token_id")

        logger.info(f"Model card version {new_version} validated for: {model_name}")

        metadata_json = json.dumps(standardized_metadata, indent=2, sort_keys=True, default=str)
        file_key = f"model-cards/{model_name}_{new_version}_{datetime.utcnow().timestamp()}.json"

        metadata_uri = await upload_to_minio(
            file_key,
            metadata_json.encode('utf-8'),
            content_type="application/json"
        )

        tx_result = await create_model_card_on_chain(
            creator=request.developer_address,
            metadata_uri=metadata_uri,
            metadata_json=metadata_json
        )
        token_id = tx_result["token_id"]
        content_hash = tx_result.get("content_hash")

        await track_model_card_in_neo4j(
            token_id=token_id,
            status="Created",
            metadata=standardized_metadata,
            address=request.developer_address,
            action="NFTMinted",
            additional_data={
                "tx_hash": tx_result.get("tx_hash"),
                "metadata_uri": metadata_uri,
                "parent_token_id": parent_token_id,
                "is_new_version": True
            },
            creator_uuid=request.creator_uuid
        )

        await create_or_update_model_lineage(
            organization=developer_org,
            model_name=model_name,
            token_id=token_id
        )

        if parent_token_id is not None:
            link_query = """
            MATCH (parent:ModelCard {token_id: $parent_id})
            MATCH (child:ModelCard {token_id: $child_id})
            MERGE (parent)-[r:HAS_VERSION]->(child)
            SET r.created_at = datetime()
            """
            await neo4j_conn.execute(link_query, {
                "parent_id": parent_token_id,
                "child_id": token_id
            })

        if deprecated_predecessor:
            await create_supersession_relationship(
                deprecated_token_id=deprecated_predecessor.get("token_id"),
                successor_token_id=token_id,
                reason="New version created to supersede deprecated model"
            )

        return {
            "success": True,
            "message": f"Model card version {new_version} created as NFT #{token_id}",
            "token_id": token_id,
            "version": new_version,
            "previous_version": current_version if parent_token_id else None,
            "parent_token_id": parent_token_id,
            "supersedes_deprecated": deprecated_predecessor.get("token_id") if deprecated_predecessor else None,
            "metadata_uri": metadata_uri,
            "content_hash": content_hash,
            "tx_hash": tx_result.get("tx_hash"),
            "status": "Created",
            "model_name": model_name,
            "developer": developer_org
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create model card version")
        raise HTTPException(
            status_code=_http_status_for(e),
            detail=_clean_create_error(e),
        )
