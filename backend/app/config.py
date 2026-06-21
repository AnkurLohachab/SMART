from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from pydantic import Field
from typing import Optional
import urllib.parse


class Settings(BaseSettings):
    """App configuration. SMART_* are current names; legacy names kept for compatibility."""

    SMART_ACCOUNT_FACTORY_ADDRESS: str = Field(default="", env="SMART_ACCOUNT_FACTORY_ADDRESS")

    SMART_RELAYER_ADDRESS: str = Field(default="", env="SMART_RELAYER_ADDRESS")

    SMART_LIFECYCLE_ADDRESS: str = Field(default="", env="SMART_LIFECYCLE_ADDRESS")

    SMART_LIFECYCLE_RELAYER_ADDRESS: str = Field(default="", env="SMART_LIFECYCLE_RELAYER_ADDRESS")

    SMART_MODEL_CARD_SBT_ADDRESS: str = Field(default="", env="SMART_MODEL_CARD_SBT_ADDRESS")

    SMART_IDENTITY_REGISTRY_ADDRESS: str = Field(default="", env="SMART_IDENTITY_REGISTRY_ADDRESS")

    SMART_USERNAME_REGISTRY_ADDRESS: str = Field(default="", env="SMART_USERNAME_REGISTRY_ADDRESS")

    SMART_PAYMASTER_ADDRESS: str = Field(default="", env="SMART_PAYMASTER_ADDRESS")

    MODEL_CARD_REGISTRY_ADDRESS: str = Field(default="", env="MODEL_CARD_REGISTRY_ADDRESS")

    ENTRYPOINT_ADDRESS: str = Field(default="0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789", env="ENTRYPOINT_ADDRESS")

    CONTRACT_ADDRESS: str = Field(default="", env="CONTRACT_ADDRESS")
    GASLESS_RELAYER_ADDRESS: str = Field(default="", env="GASLESS_RELAYER_ADDRESS")
    MLUCE_ADDRESS: str = Field(default="", env="MLUCE_ADDRESS")
    MLUCE_GASLESS_RELAYER_ADDRESS: str = Field(default="", env="MLUCE_GASLESS_RELAYER_ADDRESS")
    MODEL_CARD_SBT_ADDRESS: str = Field(default="", env="MODEL_CARD_SBT_ADDRESS")
    IDENTITY_REGISTRY_ADDRESS: str = Field(default="", env="IDENTITY_REGISTRY_ADDRESS")
    ROLE_ACCOUNT_FACTORY_ADDRESS: str = Field(default="", env="ROLE_ACCOUNT_FACTORY_ADDRESS")
    ROLE_ACCOUNT_IMPL_ADDRESS: str = Field(default="", env="ROLE_ACCOUNT_IMPL_ADDRESS")
    MODEL_CARD_PAYMASTER_ADDRESS: str = Field(default="", env="MODEL_CARD_PAYMASTER_ADDRESS")
    USERNAME_REGISTRY_ADDRESS: str = Field(default="", env="USERNAME_REGISTRY_ADDRESS")

    PRIVATE_KEY: str = Field(default="", env="PRIVATE_KEY")
    WALLET_ADDRESS: str = Field(default="", env="WALLET_ADDRESS")
    INFURA_URL: str = Field(default="http://localhost:8545", env="INFURA_URL")
    CHAIN_ID: int = Field(default=31337, env="CHAIN_ID")
    MAX_GAS_PRICE: int = Field(50, env="MAX_GAS_PRICE")

    PRIVATE_KEY_PATH: Path = Field(default=Path("/app/keys/private_key.pem"), env="PRIVATE_KEY_PATH")
    PUBLIC_KEY_PATH: Path = Field(default=Path("/app/keys/public_key.pem"), env="PUBLIC_KEY_PATH")

    OTP_EXPIRY_SECONDS: int = Field(300, env="OTP_EXPIRY_SECONDS")
    TOKEN_EXPIRY_SECONDS: int = Field(3600, env="TOKEN_EXPIRY_SECONDS")

    MINIO_ENDPOINT: str = Field(default="minio:9000", env="MINIO_ENDPOINT")
    MINIO_ACCESS_KEY: str = Field(default="minioadmin", env="MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY: str = Field(default="minioadmin", env="MINIO_SECRET_KEY")
    MINIO_BUCKET_NAME: str = Field(default="model-cards", env="MINIO_BUCKET_NAME")
    MINIO_SECURE: bool = Field(default=False, env="MINIO_SECURE")
    MINIO_URL: str = Field(default="http://minio:9000", env="MINIO_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.SMART_ACCOUNT_FACTORY_ADDRESS and self.CONTRACT_ADDRESS:
            self.SMART_ACCOUNT_FACTORY_ADDRESS = self.CONTRACT_ADDRESS
        if not self.SMART_RELAYER_ADDRESS and self.GASLESS_RELAYER_ADDRESS:
            self.SMART_RELAYER_ADDRESS = self.GASLESS_RELAYER_ADDRESS
        if not self.SMART_LIFECYCLE_ADDRESS and self.MLUCE_ADDRESS:
            self.SMART_LIFECYCLE_ADDRESS = self.MLUCE_ADDRESS
        if not self.SMART_LIFECYCLE_RELAYER_ADDRESS and self.MLUCE_GASLESS_RELAYER_ADDRESS:
            self.SMART_LIFECYCLE_RELAYER_ADDRESS = self.MLUCE_GASLESS_RELAYER_ADDRESS
        if not self.SMART_MODEL_CARD_SBT_ADDRESS and self.MODEL_CARD_SBT_ADDRESS:
            self.SMART_MODEL_CARD_SBT_ADDRESS = self.MODEL_CARD_SBT_ADDRESS
        if not self.SMART_IDENTITY_REGISTRY_ADDRESS and self.IDENTITY_REGISTRY_ADDRESS:
            self.SMART_IDENTITY_REGISTRY_ADDRESS = self.IDENTITY_REGISTRY_ADDRESS
        if not self.SMART_USERNAME_REGISTRY_ADDRESS and self.USERNAME_REGISTRY_ADDRESS:
            self.SMART_USERNAME_REGISTRY_ADDRESS = self.USERNAME_REGISTRY_ADDRESS
        if not self.SMART_PAYMASTER_ADDRESS and self.MODEL_CARD_PAYMASTER_ADDRESS:
            self.SMART_PAYMASTER_ADDRESS = self.MODEL_CARD_PAYMASTER_ADDRESS


settings = Settings()
