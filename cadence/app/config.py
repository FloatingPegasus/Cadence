from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from math import isfinite

from pydantic import EmailStr, Field, SecretStr, TypeAdapter, model_validator
from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url


JWT_ALGORITHM = "HS256"
TEST_SIGNING_VALUE = "cadence-test-only-secret-key-32-bytes"
INSECURE_SECRET_KEYS = frozenset(
    {
        "",
        "change-me-in-production",
        "replace-with-a-long-random-value",
        TEST_SIGNING_VALUE,
    }
)
EMAIL_ADAPTER = TypeAdapter(EmailStr)


def _validate_database_url(value: str) -> str:
    candidate = value.strip()
    try:
        parsed = make_url(candidate)
    except Exception as error:
        raise ValueError(
            "CADENCE_DATABASE_URL must be a valid PostgreSQL psycopg URL"
        ) from error
    if (
        parsed.get_backend_name() != "postgresql"
        or parsed.get_driver_name() != "psycopg"
        or not parsed.database
    ):
        raise ValueError(
            "CADENCE_DATABASE_URL must use postgresql+psycopg:// and include a database"
        )
    return candidate


def _validate_http_url(
    value: str,
    *,
    allow_path: bool,
    allow_insecure_loopback: bool = False,
    allow_insecure_http: bool = False,
) -> str:
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if (
        not candidate
        or parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("must be an http(s) URL without credentials or query parameters")
    try:
        if not parsed.hostname:
            raise ValueError
        parsed.port  # Force malformed ports to fail validation.
    except ValueError as error:
        raise ValueError("must contain a valid host and port") from error
    is_loopback = parsed.hostname.lower().rstrip(".") in {
        "localhost",
        "127.0.0.1",
        "::1",
    }
    if parsed.scheme == "http" and not (
        allow_insecure_http or (allow_insecure_loopback and is_loopback)
    ):
        raise ValueError("public URLs must use HTTPS")
    if not allow_path and parsed.path not in {"", "/"}:
        raise ValueError("must contain only an origin (scheme and host)")
    if any(char.isspace() for char in candidate):
        raise ValueError("must not contain whitespace")
    return candidate.rstrip("/") if allow_path else f"{parsed.scheme}://{parsed.netloc}"


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://cadence:cadence-local-password@localhost:5432/cadence"
    )
    secret_key: str = ""
    algorithm: str = JWT_ALGORITHM
    access_token_expire_minutes: int = 60 * 24 * 7

    test_mode: bool = False
    dev_mode: bool = False
    dev_email: str = ""
    dev_password: SecretStr = SecretStr("")
    legacy_dev_usernames: str = Field(
        default="",
        validation_alias="CADENCE_DEV_USERNAMES",
        exclude=True,
    )

    ai_enabled: bool = False
    ai_provider: str = "nvidia"
    ai_base_url: str = "https://integrate.api.nvidia.com/v1"
    ai_api_key: str = ""
    ai_catalog_refresh_minutes: int = 360
    ai_request_timeout_seconds: float = 45.0
    embedding_enabled: bool = False
    embedding_model: str = "nvidia/nv-embedqa-e5-v5"
    embedding_dimensions: int = 1024
    embedding_input_max_chars: int = 4_000
    embedding_request_timeout_seconds: float = 15.0

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
    auth_rate_limit_window_seconds: int = 60
    auth_register_rate_limit: int = 5
    auth_login_rate_limit: int = 10
    auth_verification_rate_limit: int = 20
    auth_verification_resend_rate_limit: int = 5
    auth_rate_limit_backend: Literal["memory", "redis"] = "memory"
    redis_url: str = ""
    redis_key_prefix: str = "cadence:rate-limit"
    redis_connect_timeout_seconds: float = 5.0
    redis_socket_timeout_seconds: float = 5.0

    model_config = {
        "env_prefix": "CADENCE_",
        "env_file": str(Path(__file__).parent.parent.parent / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "hide_input_in_errors": True,
    }

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        self.database_url = _validate_database_url(self.database_url)
        self.secret_key = self.secret_key.strip()
        if self.algorithm != JWT_ALGORITHM:
            raise ValueError(
                f"CADENCE_ALGORITHM must be {JWT_ALGORITHM}; other algorithms are not supported"
            )
        if self.test_mode:
            if not self.secret_key or self.secret_key in INSECURE_SECRET_KEYS:
                self.secret_key = TEST_SIGNING_VALUE
        elif (
            not self.secret_key
            or self.secret_key in INSECURE_SECRET_KEYS
            or len(self.secret_key) < 32
        ):
            raise ValueError(
                "CADENCE_SECRET_KEY must be a random value of at least 32 "
                "characters outside test mode. Generate one with "
                "`python3 -c 'import secrets; print(secrets.token_urlsafe(48))'` "
                "and set it in the project-root .env"
            )

        self.frontend_base_url = _validate_http_url(
            self.frontend_base_url,
            allow_path=True,
            allow_insecure_loopback=True,
            allow_insecure_http=self.test_mode,
        )
        try:
            self.ai_base_url = _validate_http_url(
                self.ai_base_url,
                allow_path=True,
                allow_insecure_loopback=True,
                allow_insecure_http=self.test_mode,
            )
        except ValueError as error:
            raise ValueError(f"CADENCE_AI_BASE_URL {error}") from error
        origins = self.allowed_cors_origins
        if not origins:
            raise ValueError("CADENCE_CORS_ORIGINS must contain at least one origin")
        if any(origin == "*" for origin in origins):
            raise ValueError(
                "CADENCE_CORS_ORIGINS cannot use '*' when authorization is enabled"
            )
        self.cors_origins = ",".join(
            _validate_http_url(
                origin,
                allow_path=False,
                allow_insecure_loopback=True,
                allow_insecure_http=self.test_mode,
            )
            for origin in origins
        )

        self.dev_email = self.dev_email.strip().casefold()
        if self.dev_mode:
            try:
                self.dev_email = str(
                    EMAIL_ADAPTER.validate_python(self.dev_email)
                ).casefold()
            except ValueError as error:
                raise ValueError(
                    "CADENCE_DEV_EMAIL must be a valid email address when dev mode is enabled"
                ) from error
            dev_password = self.dev_password.get_secret_value()
            if not 8 <= len(dev_password) <= 128:
                raise ValueError(
                    "CADENCE_DEV_PASSWORD must contain between 8 and 128 characters when dev mode is enabled"
                )
            if len(dev_password.encode("utf-8")) > 72:
                raise ValueError(
                    "CADENCE_DEV_PASSWORD cannot exceed 72 UTF-8 bytes"
                )
        if self.access_token_expire_minutes <= 0:
            raise ValueError("CADENCE_ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
        if self.verification_token_expire_hours <= 0:
            raise ValueError("CADENCE_VERIFICATION_TOKEN_EXPIRE_HOURS must be positive")
        for field_name in (
            "auth_rate_limit_window_seconds",
            "auth_register_rate_limit",
            "auth_login_rate_limit",
            "auth_verification_rate_limit",
            "auth_verification_resend_rate_limit",
        ):
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be positive")
        for field_name in (
            "redis_connect_timeout_seconds",
            "redis_socket_timeout_seconds",
            "embedding_request_timeout_seconds",
        ):
            timeout = getattr(self, field_name)
            if not isfinite(timeout) or timeout <= 0:
                raise ValueError(f"{field_name} must be a finite positive number")
        if self.embedding_dimensions != 1024:
            raise ValueError("CADENCE_EMBEDDING_DIMENSIONS must be 1024")
        if not 256 <= self.embedding_input_max_chars <= 32_000:
            raise ValueError(
                "CADENCE_EMBEDDING_INPUT_MAX_CHARS must be between 256 and 32000"
            )
        if not self.embedding_model.strip():
            raise ValueError("CADENCE_EMBEDDING_MODEL must not be blank")
        self.embedding_model = self.embedding_model.strip()
        self.redis_url = self.redis_url.strip()
        self.redis_key_prefix = self.redis_key_prefix.strip()
        if not self.redis_key_prefix or len(self.redis_key_prefix) > 64:
            raise ValueError(
                "CADENCE_REDIS_KEY_PREFIX must contain between 1 and 64 characters"
            )
        if any(
            character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:_-"
            for character in self.redis_key_prefix
        ):
            raise ValueError(
                "CADENCE_REDIS_KEY_PREFIX may contain only letters, numbers, ':', '_' or '-'"
            )
        if self.auth_rate_limit_backend == "redis":
            parsed_redis_url = urlsplit(self.redis_url)
            if (
                parsed_redis_url.scheme not in {"redis", "rediss"}
                or not parsed_redis_url.netloc
                or parsed_redis_url.query
                or parsed_redis_url.fragment
                or any(character.isspace() for character in self.redis_url)
            ):
                raise ValueError(
                    "CADENCE_REDIS_URL must be a redis:// or rediss:// URL without a query or fragment"
                )
            try:
                parsed_redis_url.port
            except ValueError as error:
                raise ValueError("CADENCE_REDIS_URL must contain a valid port") from error
        return self

    @property
    def sync_database_url(self) -> str:
        return self.database_url

    @property
    def resolved_backup_dir(self) -> Path:
        path = self.backup_dir.expanduser()
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

settings = Settings()
