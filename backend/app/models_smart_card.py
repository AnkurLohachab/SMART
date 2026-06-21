"""API request/response models for the model-card endpoints."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ModelDetails(BaseModel):
    """Section 1: Model Details."""
    model_name: str = Field(..., alias="Model Name")
    version: str = Field(..., alias="Version")
    developer_organization: str = Field(..., alias="Developer / Organization")
    release_date: str = Field(..., alias="Release Date", pattern=r"^\d{4}-\d{2}-\d{2}$")
    description: str = Field(..., alias="Description")
    clinical_function: str = Field(..., alias="Clinical Function")
    intended_purpose: Optional[str] = Field(None, alias="Intended Purpose")
    information_significance: Optional[str] = Field(None, alias="Information Significance")
    algorithms_used: str = Field(..., alias="Algorithm(s) Used")
    gmdn_code: Optional[str] = Field(None, alias="GMDN Code")
    basic_udi_di: Optional[str] = Field(None, alias="Basic UDI-DI")
    udi_di: Optional[str] = Field(None, alias="UDI-DI")
    regulatory_classifications: Optional[List[Dict[str, str]]] = Field(default_factory=list, alias="Regulatory Classifications")
    licensing: str = Field(..., alias="Licensing")
    support_contact: str = Field(..., alias="Support Contact")
    literature_references: Optional[List[str]] = Field(default_factory=list, alias="Literature References")
    clinical_study_references: Optional[List[str]] = Field(default_factory=list, alias="Clinical Study References")
    logo_image: Optional[str] = Field(None, alias="Logo / Image (optional)")

    class Config:
        populate_by_name = True


class ModelCardCreate(BaseModel):
    """Request model for creating a model card."""
    developer_address: str = Field(..., description="Ethereum address of the developer")
    metadata: Dict[str, Any] = Field(..., description="Model card JSON matching the smart-model-card schema")
    creator_uuid: Optional[str] = Field(None, description="UUID of the user creating the model card")


class ModelCardResponse(BaseModel):
    """Response model for model card operations."""
    success: bool
    token_id: Optional[int] = None
    status: Optional[str] = None
    metadata_uri: Optional[str] = None
    tx_hash: Optional[str] = None
    message: Optional[str] = None
