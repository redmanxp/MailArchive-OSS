"""MailArchive application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment / .env (+ optional file overrides)."""

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MailArchive"
    app_env: str = "development"
    app_debug: bool = False
    app_url: str = "http://localhost:5175"
    api_url: str = "http://localhost:18100"
    secret_key: str = "change-me-to-a-long-random-string"
    bind_host: str = "0.0.0.0"
    bind_port: int = 18100

    # sqlite | mysql
    db_engine: str = "sqlite"
    database_url: str | None = None
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "mailarchive"
    mysql_password: str = "change-me-db-password"
    mysql_database: str = "mailarchive"

    jwt_secret_key: str = "change-me-jwt-secret"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    data_encryption_key: str = "change-me-fernet-key"
    storage_root: str = str(ROOT_DIR / "storage")
    # filesystem | s3 (MinIO / R2 / Wasabi / AWS)
    storage_backend: str = "filesystem"
    s3_endpoint_url: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "mailarchive"
    s3_region: str = "us-east-1"
    s3_force_path_style: bool = True
    s3_prefix: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@example.com"
    smtp_reply_to: str = ""
    smtp_timeout_seconds: int = 30
    smtp_tls: bool = True

    install_tenant_name: str = "Acme"
    install_tenant_slug: str = "acme"
    install_admin_email: str = "admin@example.com"
    install_admin_name: str = "Administrator"

    # single = one org (hide tenant on login); multi = require/use tenant slug
    tenant_mode: str = "single"

    feature_public_register: bool = False

    rate_limit_enabled: bool = True
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60

    cors_origins: str = "http://localhost:5175,http://127.0.0.1:5175"

    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant_id: str = "common"
    microsoft_redirect_uri: str = (
        "http://localhost:18100/api/v1/accounts/microsoft/oauth/callback"
    )
    microsoft_object_id: str = ""
    microsoft_secret_id: str = ""
    microsoft_scopes: str = (
        "openid profile offline_access User.Read Mail.ReadWrite MailboxSettings.Read"
    )

    def build_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        if self.db_engine == "sqlite":
            if Path("/data").is_dir():
                return "sqlite:////data/mailarchive.db"
            db_path = ROOT_DIR / "data" / "mailarchive.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{db_path}"
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    from app.infrastructure.system_overrides import apply_overrides

    return apply_overrides(Settings())


def reload_settings() -> Settings:
    """Clear cache and reload env + file overrides (storage / Graph hot path)."""
    get_settings.cache_clear()
    return get_settings()
