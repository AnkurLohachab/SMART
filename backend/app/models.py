
from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import List, Optional, Dict, Any

class UserRegistrationRequest(BaseModel):
    uuid: Optional[str] = Field(None, description="Unique identifier for the user registration. Leave empty for auto-generation.")
    username: Optional[str] = Field(None, description="Optional display name for the user.")
    email: Optional[str] = Field(None, description="Optional contact email for the user.")

class UserVerifyRequest(BaseModel):
    uuid: str = Field(..., description="UUID provided during registration.")
    otp: str = Field(..., description="One-Time Password sent to the user.")
    @field_validator('otp')
    def otp_must_be_six_digits(cls, v):
        if not v.isdigit() or len(v) != 6:
            raise ValueError('OTP must be a 6-digit number')
        return v

    @field_validator('uuid')
    def uuid_must_not_be_empty(cls, v):
        if not v:
            raise ValueError('UUID must not be empty')
        return v
    
class LoginRequest(BaseModel):
    uuid: str = Field(..., description="User's UUID")
    role: str = Field(..., description="Role selected by the user")

class LoginResponse(BaseModel):
    message: str
    otp: Optional[str] = Field(None, description="One-Time Password for authentication")

class AuthenticateRequest(BaseModel):
    uuid: str = Field(..., description="User's UUID")
    role: str = Field(..., description="Role selected by the user")
    otp: str = Field(..., description="One-Time Password received during login")

class UserProfileUpdateRequest(BaseModel):
    username: Optional[str] = Field(None, description="Display name for the user.")
    email: Optional[str] = Field(None, description="Contact email for the user.")

class WalletInfo(BaseModel):
    eoa_address: Optional[str] = Field(None, description="User's EOA wallet address")
    smart_account: Optional[str] = Field(None, description="Smart account address for the selected role")
    role: str = Field(..., description="The role associated with the smart account")

class AuthenticateResponse(BaseModel):
    message: str
    token: str
    wallet_info: Optional[WalletInfo] = Field(None, description="Wallet addresses for the authenticated user") 

class UploadModelCardRequest(BaseModel):
    custom_account: str = Field(..., description="The CustomAccount address of the user.")
    model_data: dict = Field(..., description="The JSON data of the model card.")
    version_token_id: Optional[int] = Field(None, description="The token ID of the base model card for versioning.")

class UploadModelCardResponse(BaseModel):
    message: str
    token_id: int
    storage_url: str


class ModelAuthors(BaseModel):
    name: str
    contact: str

class ModelDetail(BaseModel):
    summary: str
    motivation: str
    tasks: str
    use_cases: str
    benefits: str

class ModelSnapshot(BaseModel):
    snapshot_link: HttpUrl

class ModelArchitecture(BaseModel):
    description: str
    input_specs: str
    output_specs: str

class Usage(BaseModel):
    applications: str
    benefits: str
    known_caveats: str

class ModelCreators(BaseModel):
    contact: str
    authors: List[ModelAuthors]
    citation: Optional[HttpUrl] = None

class SystemType(BaseModel):
    description: str
    upstream_dependencies: str
    downstream_dependencies: str

class ImplementationFrameworks(BaseModel):
    training_hardware_software: str
    deployment_hardware_software: str

class ComputeRequirements(BaseModel):
    fine_tuning_chips: Optional[int] = None
    fine_tuning_training_time_days: Optional[float] = None
    fine_tuning_total_computation: Optional[float] = None
    fine_tuning_performance_tflops: Optional[float] = None
    fine_tuning_energy_consumption_mwh: Optional[float] = None
    inference_chips: Optional[int] = None
    inference_training_time_days: Optional[float] = None
    inference_total_computation: Optional[float] = None
    inference_performance_tflops: Optional[float] = None
    inference_energy_consumption_mwh: Optional[float] = None

class ModelCharacteristics(BaseModel):
    initialization: str
    status: str
    stats: str
    training_epochs: Optional[int] = None
    dataset_name: Optional[str] = None
    size: Optional[str] = None
    version: Optional[str] = None
    weights: Optional[str] = None
    layers: Optional[int] = None
    loss: Optional[str] = None
    update_cadence: Optional[str] = None
    latency: Optional[str] = None
    pruning: Optional[Dict[str, Any]] = None
    quantization: Optional[Dict[str, Any]] = None

class DataOverview(BaseModel):
    training_dataset_snapshot: HttpUrl
    dataset_maintenance_versions: str
    instrumentation: str
    dataset_size: str
    number_of_instances: int
    number_of_fields: int
    labeled_classes: str
    number_of_labels: int
    average_labels_per_instance: float
    missing_labels: str
    additional_notes: Optional[str] = None
    data_pre_processing: str
    demographic_groups: str
    evaluation_data: str

class EvaluationResults(BaseModel):
    aggregate_evaluation_results: str
    evaluation_process: str
    evaluation_results: str

class SubgroupEvaluationResults(BaseModel):
    subgroup_evaluated: str
    evaluation_process_data: str
    evaluation_results: str

class FairnessEvaluationResults(BaseModel):
    fairness_criteria: str
    fairness_metrics_baseline: str
    fairness_results: str

class ModelUsageLimitations(BaseModel):
    sensitive_use: str
    limitations: str
    ethical_considerations_risks: str

class TermsOfArt(BaseModel):
    term: str
    definition: str
    source: HttpUrl
    interpretation: Optional[str] = None

class ReflectionsOnModel(BaseModel):
    title: str
    notes: str

class ModelData(BaseModel):
    id: str
    name: str
    version: str
    license: str
    model_link: HttpUrl
    documentation_link: HttpUrl
    authors: List[ModelAuthors]
    model_detail: ModelDetail
    model_snapshot: ModelSnapshot
    model_architecture: ModelArchitecture
    usage: Usage
    model_creators: ModelCreators
    system_type: SystemType
    implementation_frameworks: ImplementationFrameworks
    compute_requirements: ComputeRequirements
    model_characteristics: ModelCharacteristics
    data_overview: DataOverview
    evaluation_results: EvaluationResults
    subgroup_evaluation_results: List[SubgroupEvaluationResults]
    fairness_evaluation_results: FairnessEvaluationResults
    model_usage_limitations: ModelUsageLimitations
    terms_of_art: List[TermsOfArt]
    reflections_on_model: List[ReflectionsOnModel]


