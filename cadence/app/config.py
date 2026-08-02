from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///" + str(
        Path(__file__).parent.parent / "data" / "database.db"
    )
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    test_mode: bool = False
    dev_mode: bool = False
    dev_usernames: str = ""

    ai_enabled: bool = False
    ai_provider: str = "nvidia"
    ai_base_url: str = "https://integrate.api.nvidia.com/v1"
    ai_api_key: str = ""
    ai_catalog_refresh_minutes: int = 360
    ai_request_timeout_seconds: float = 45.0

    brevo_api_key: str = ""
    from_email: str = "no-reply@cadence.app"
    from_name: str = "Cadence"

    frontend_base_url: str = "http://localhost:3001"
    cors_origins: str = "http://localhost:3001"
    serve_frontend: bool = False
    frontend_dist_dir: Path = (
        Path(__file__).resolve().parents[2] / "front" / "dist"
    )
    verification_token_expire_hours: int = 24
    backup_dir: Path = (
        Path(__file__).parent.parent / "data" / "backups"
    )
    backup_retention_count: int = 10
    runtime_lock_path: Path = (
        Path(__file__).parent.parent / "data" / "cadence.lock"
    )

    model_config = {
        "env_prefix": "CADENCE_",
        "env_file": str(Path(__file__).parent.parent.parent / ".env"),
        "env_file_encoding": "utf-8",
    }

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+aiosqlite", "")

    @property
    def resolved_backup_dir(self) -> Path:
        path = self.backup_dir.expanduser()
        if path.is_absolute():
            return path
        repository_root = Path(__file__).resolve().parents[2]
        return repository_root / path

    @property
    def resolved_runtime_lock_path(self) -> Path:
        path = self.runtime_lock_path.expanduser()
        if path.is_absolute():
            return path
        repository_root = Path(__file__).resolve().parents[2]
        return repository_root / path

    @property
    def resolved_frontend_dist_dir(self) -> Path:
        path = self.frontend_dist_dir.expanduser()
        if path.is_absolute():
            return path
        repository_root = Path(__file__).resolve().parents[2]
        return repository_root / path

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def developer_usernames(self) -> set[str]:
        return {
            username.strip()
            for username in self.dev_usernames.split(",")
            if username.strip()
        }


settings = Settings()
