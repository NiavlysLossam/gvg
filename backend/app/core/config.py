from pathlib import Path
from typing import List, Union, Optional
from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "GVG (Gestion de Vide-Greniers)"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # Business / Anti-Hoarding Quotas
    MAX_CART_SPOTS_PER_SESSION: int = 5

    # Database
    DATABASE_URL: str = "postgresql+psycopg://gvg:gvg_secret@localhost:5432/gvg"
    
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # JWT / Authentication
    JWT_SECRET_KEY: str = "gvg_default_insecure_jwt_secret_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # SMTP / Emails
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    EMAILS_FROM_EMAIL: str = "noreply@gvg.local"
    EMAILS_FROM_NAME: str = "GVG - Vide-Greniers"
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    # Uploads
    UPLOAD_DIR: str = "uploads"

    @property
    def upload_dir_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        if not p.is_absolute():
            backend_root = Path(__file__).resolve().parent.parent.parent
            p = backend_root / self.UPLOAD_DIR
        return p
    
    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.strip().startswith("["):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        raise ValueError(v)

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        env = (self.ENVIRONMENT or "development").strip().lower()
        if env not in ("development", "test"):
            insecure_defaults = (
                "gvg_default_insecure_jwt_secret_key_change_in_production",
                "changer_cette_cle_secrete_jwt_par_une_chaine_aleatoire_tres_longue",
            )
            key = self.JWT_SECRET_KEY or ""
            if not key or key in insecure_defaults or "changer_cette_cle" in key or "insecure_jwt_secret" in key:
                raise ValueError(
                    f"CRITICAL SECURITY CONFIGURATION ERROR: JWT_SECRET_KEY must be set to a secure custom secret in {env}! "
                    "Refusing to start with a default or template insecure key."
                )
            if len(key) < 32:
                raise ValueError(
                    f"CRITICAL SECURITY CONFIGURATION ERROR: JWT_SECRET_KEY must be at least 32 characters long in {env} (got {len(key)})."
                )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()

