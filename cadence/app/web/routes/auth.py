from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import bcrypt as _bcrypt
import jwt
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import JWT_ALGORITHM, _validate_http_url, settings
from ...extensions import get_db
from ...persistence.models.user import User
from ...services.email import EmailDeliveryError, send_verification_email
from ...services.rate_limit import enforce_auth_rate_limit

router = APIRouter(tags=["auth"])
security = HTTPBearer(auto_error=False)
ISSUER = "cadence"
TOKEN_PURPOSES = frozenset({"access", "verify_email"})
SESSION_COOKIE_NAME = "cadence_session"
CSRF_COOKIE_NAME = "cadence_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
SESSION_COOKIE_MAX_AGE_CAP_SECONDS = 30 * 24 * 60 * 60
UNSAFE_HTTP_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_DUMMY_PASSWORD_HASH = _bcrypt.hashpw(
    b"cadence-invalid-login-password", _bcrypt.gensalt()
)


class InvalidSessionError(Exception):
    """Raised when a browser session cookie cannot authenticate."""


def _normalize_username(
    value: str,
    *,
    minimum_length: int,
    maximum_length: int = 80,
) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Username cannot be blank")
    if not minimum_length <= len(normalized) <= maximum_length:
        raise ValueError(
            f"Username must be between {minimum_length} and {maximum_length} characters"
        )
    if any(
        ord(character) < 32 or ord(character) == 127
        for character in normalized
    ):
        raise ValueError("Username cannot contain control characters")
    return normalized


def _normalize_login_identifier(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Username or email cannot be blank")
    if len(normalized) > 255:
        raise ValueError("Username or email cannot exceed 255 characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValueError("Username or email cannot contain control characters")
    return normalized


def _validate_password_bytes(value: str) -> str:
    # bcrypt only uses 72 bytes. Reject longer values rather than silently
    # authenticating two different passwords as the same credential.
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password cannot exceed 72 UTF-8 bytes")
    return value


class RegisterBody(BaseModel):
    username: str = Field(max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return _normalize_username(value, minimum_length=3)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().casefold()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_bytes(value)


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return _normalize_login_identifier(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_bytes(value)


class VerifyBody(BaseModel):
    token: str = Field(min_length=1, max_length=2048)


class ResendVerificationBody(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().casefold()


def _create_token(
    user_id: int,
    *,
    purpose: str = "access",
    expires_delta: timedelta | None = None,
    csrf_token: str | None = None,
    developer: bool = False,
) -> str:
    if purpose not in TOKEN_PURPOSES:
        raise ValueError("Unknown token purpose")
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    if expires_delta <= timedelta(0):
        raise ValueError("Token lifetime must be positive")
    if settings.algorithm != JWT_ALGORITHM:
        raise RuntimeError("Unsupported JWT algorithm configuration")
    now = datetime.now(timezone.utc)
    expire = datetime.now(timezone.utc) + expires_delta
    claims = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "iss": ISSUER,
        "jti": secrets.token_urlsafe(18),
        "purpose": purpose,
    }
    if csrf_token is not None:
        claims["csrf"] = csrf_token
    if developer:
        claims["developer"] = True
    return jwt.encode(
        claims,
        settings.secret_key,
        algorithm=JWT_ALGORITHM,
    )


def _decode_token(token: str, *, purpose: str) -> dict:
    if purpose not in TOKEN_PURPOSES:
        raise jwt.PyJWTError("Unknown token purpose")
    if settings.algorithm != JWT_ALGORITHM:
        raise jwt.PyJWTError("Unsupported JWT algorithm configuration")
    header = jwt.get_unverified_header(token)
    if header.get("alg") != JWT_ALGORITHM:
        raise jwt.PyJWTError("Unsupported JWT algorithm")
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[JWT_ALGORITHM],
        issuer=ISSUER,
        options={"require": ["exp", "iat", "iss", "jti", "sub"]},
    )
    if payload.get("purpose") != purpose:
        raise jwt.PyJWTError("Invalid token purpose")
    subject = payload.get("sub")
    if (
        not isinstance(subject, str)
        or not subject.isdecimal()
        or int(subject) <= 0
    ):
        raise jwt.PyJWTError("Invalid token subject")
    return payload


def is_developer(user: User) -> bool:
    return (
        settings.dev_mode
        and bool(settings.dev_email)
        and secrets.compare_digest(user.email.casefold(), settings.dev_email)
        and getattr(user, "_cadence_developer_session", False) is True
    )


def _mark_developer_session(user: User, enabled: bool) -> None:
    user._cadence_developer_session = (
        enabled
        and settings.dev_mode
        and bool(settings.dev_email)
        and secrets.compare_digest(user.email.casefold(), settings.dev_email)
    )


def _is_dev_login(identifier: str) -> bool:
    return (
        settings.dev_mode
        and bool(settings.dev_email)
        and secrets.compare_digest(identifier.casefold(), settings.dev_email)
    )


async def _get_or_create_dev_user(db: AsyncSession) -> User:
    user = await db.scalar(
        select(User).where(func.lower(User.email) == settings.dev_email)
    )
    if user is not None:
        if not user.is_verified:
            user.is_verified = True
            await db.commit()
        return user

    username = "developer"
    username_in_use = await db.scalar(
        select(User.id).where(User.username == username)
    )
    if username_in_use is not None:
        email_digest = sha256(
            settings.dev_email.encode("utf-8")
        ).hexdigest()[:12]
        username = f"developer-{email_digest}"

    random_database_password = secrets.token_urlsafe(48)
    hashed_password = await run_in_threadpool(
        lambda: _bcrypt.hashpw(
            random_database_password.encode(), _bcrypt.gensalt()
        ).decode()
    )
    user = User(
        username=username,
        email=settings.dev_email,
        hashed_password=hashed_password,
        is_verified=True,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        user = await db.scalar(
            select(User).where(func.lower(User.email) == settings.dev_email)
        )
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Development account could not be prepared",
            ) from error
    await db.refresh(user)
    return user


def _session_cookie_max_age() -> int:
    configured_seconds = settings.access_token_expire_minutes * 60
    return max(1, min(configured_seconds, SESSION_COOKIE_MAX_AGE_CAP_SECONDS))


def _secure_cookies_for_deployment() -> bool:
    return urlsplit(settings.frontend_base_url).scheme == "https"


def _set_auth_cookies(
    response: Response,
    *,
    session_token: str,
    csrf_token: str,
) -> None:
    cookie_options = {
        "max_age": _session_cookie_max_age(),
        "secure": _secure_cookies_for_deployment(),
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_token,
        httponly=True,
        **cookie_options,
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        httponly=False,
        **cookie_options,
    )


def _clear_auth_cookies(response: Response) -> None:
    cookie_options = {
        "max_age": 0,
        "expires": "Thu, 01 Jan 1970 00:00:00 GMT",
        "secure": _secure_cookies_for_deployment(),
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie(
        SESSION_COOKIE_NAME,
        "",
        httponly=True,
        **cookie_options,
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        "",
        httponly=False,
        **cookie_options,
    )


def _require_session_csrf(request: Request, payload: dict) -> None:
    if request.method.upper() not in UNSAFE_HTTP_METHODS:
        return
    signed_csrf = payload.get("csrf")
    cookie_csrf = request.cookies.get(CSRF_COOKIE_NAME, "")
    header_csrf = request.headers.get(CSRF_HEADER_NAME, "")
    if not all(
        isinstance(value, str) and value
        for value in (signed_csrf, cookie_csrf, header_csrf)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )
    if not (
        secrets.compare_digest(header_csrf, cookie_csrf)
        and secrets.compare_digest(cookie_csrf, signed_csrf)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )


async def _authenticate_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> User:
    is_cookie_auth = credentials is None
    token = (
        request.cookies.get(SESSION_COOKIE_NAME)
        if is_cookie_auth
        else credentials.credentials
    )
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        payload = _decode_token(token, purpose="access")
    except (jwt.PyJWTError, ValueError):
        if is_cookie_auth:
            raise InvalidSessionError from None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    if is_cookie_auth:
        _require_session_csrf(request, payload)

    user_id = int(payload.get("sub", 0))
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        if is_cookie_auth:
            raise InvalidSessionError
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    _mark_developer_session(user, payload.get("developer") is True)
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Request a new verification email.",
        )
    return user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await _authenticate_current_user(request, credentials, db)


async def require_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await _authenticate_current_user(request, credentials, db)


@router.get("/auth/me")
async def me(current_user: User = Depends(require_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "is_verified": current_user.is_verified,
        "is_developer": is_developer(current_user),
        "ai_processing_consent": current_user.ai_processing_consent,
        "ai_redaction_enabled": current_user.ai_redaction_enabled,
    }


@router.post("/auth/register")
async def register(
    body: RegisterBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await enforce_auth_rate_limit(
        request,
        scope="register",
        identity=f"username:{body.username.casefold()}",
        limit=settings.auth_register_rate_limit,
    )
    existing = await db.execute(
        select(User).where(
            (User.username == body.username)
            | (func.lower(User.email) == body.email)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already taken",
        )

    hashed_password = await run_in_threadpool(
        lambda: _bcrypt.hashpw(body.password.encode(), _bcrypt.gensalt()).decode()
    )
    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hashed_password,
        is_verified=False,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already taken",
        ) from error
    await db.refresh(user)

    try:
        await _send_user_verification(user)
    except EmailDeliveryError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Account created, but the verification email could not be "
                "sent. Check the mail configuration, then request a new one."
            ),
        )

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_verified": False,
        "message": "Account created. Check your email to verify your address before logging in.",
    }


async def _send_user_verification(user: User) -> None:
    verification_token = _create_token(
        user.id,
        purpose="verify_email",
        expires_delta=timedelta(hours=settings.verification_token_expire_hours),
    )
    try:
        frontend_base_url = _validate_http_url(
            settings.frontend_base_url,
            allow_path=True,
            allow_insecure_loopback=True,
            allow_insecure_http=settings.test_mode,
        )
    except ValueError as error:
        raise EmailDeliveryError("Verification URL is not configured safely") from error
    verify_url = (
        f"{frontend_base_url}/verify?{urlencode({'token': verification_token})}"
    )
    await run_in_threadpool(
        send_verification_email,
        to_email=user.email,
        to_name=user.username,
        verification_url=verify_url,
    )


@router.post("/auth/verification/resend")
async def resend_verification(
    body: ResendVerificationBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await enforce_auth_rate_limit(
        request,
        scope="verification-resend",
        identity=f"email:{body.email}",
        limit=settings.auth_verification_resend_rate_limit,
        window_seconds=max(settings.auth_rate_limit_window_seconds, 900),
    )
    user = await db.scalar(
        select(User).where(func.lower(User.email) == body.email)
    )
    if user is not None and not user.is_verified:
        try:
            await _send_user_verification(user)
        except EmailDeliveryError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Verification email could not be sent. Check the mail "
                    "configuration and try again."
                ),
            )
    return {
        "message": (
            "If an unverified account uses that email, a new verification "
            "message has been sent."
        )
    }


@router.post("/auth/verify")
async def verify(
    body: VerifyBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await enforce_auth_rate_limit(
        request,
        scope="verification",
        identity=None,
        limit=settings.auth_verification_rate_limit,
    )
    try:
        payload = _decode_token(body.token, purpose="verify_email")
        user_id = int(payload.get("sub", 0))
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
    if user.is_verified:
        return {"message": "Email is already verified"}

    user.is_verified = True
    await db.commit()

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_verified": True,
    }


@router.post("/auth/login")
async def login(
    body: LoginBody,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    await enforce_auth_rate_limit(
        request,
        scope="login",
        identity=f"identifier:{body.username.casefold()}",
        limit=settings.auth_login_rate_limit,
    )
    developer_login = _is_dev_login(body.username)
    if developer_login:
        await run_in_threadpool(
            _bcrypt.checkpw,
            body.password.encode(),
            _DUMMY_PASSWORD_HASH,
        )
        if not secrets.compare_digest(
            body.password,
            settings.dev_password.get_secret_value(),
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        user = await _get_or_create_dev_user(db)
    else:
        user = await db.scalar(
            select(User).where(
                func.lower(User.email) == body.username.casefold()
            )
        )
        if user is None:
            user = await db.scalar(
                select(User).where(User.username == body.username)
            )
        password_hash = (
            user.hashed_password.encode() if user else _DUMMY_PASSWORD_HASH
        )
        password_matches = await run_in_threadpool(
            _bcrypt.checkpw,
            body.password.encode(),
            password_hash,
        )
        if not user or not password_matches:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Check your inbox for the verification link.",
        )

    csrf_token = secrets.token_urlsafe(32)
    _mark_developer_session(user, developer_login)
    token = _create_token(
        user.id,
        csrf_token=csrf_token,
        developer=developer_login,
    )
    _set_auth_cookies(
        response,
        session_token=token,
        csrf_token=csrf_token,
    )
    return {
        "user_id": user.id,
        "is_verified": user.is_verified,
        "is_developer": is_developer(user),
        "ai_processing_consent": user.ai_processing_consent,
        "ai_redaction_enabled": user.ai_redaction_enabled,
    }


@router.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
    _current_user: User = Depends(require_current_user),
):
    _clear_auth_cookies(response)
    return {"message": "Logged out"}
