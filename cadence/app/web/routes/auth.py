from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import bcrypt as _bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...extensions import get_db
from ...persistence.models.user import User
from ...services.email import EmailDeliveryError, send_verification_email

router = APIRouter(tags=["auth"])
security = HTTPBearer(auto_error=False)


class RegisterBody(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Username cannot be blank")
        return normalized


class LoginBody(BaseModel):
    username: str
    password: str


class VerifyBody(BaseModel):
    token: str


class ResendVerificationBody(BaseModel):
    email: EmailStr


def _create_token(
    user_id: int,
    *,
    purpose: str = "access",
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expire = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "purpose": purpose},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def is_developer(user: User) -> bool:
    allowed_users = settings.developer_usernames
    return settings.dev_mode and (
        not allowed_users or user.username in allowed_users
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        if payload.get("purpose") != "access":
            raise JWTError("Invalid token purpose")
        user_id = int(payload.get("sub", 0))
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Request a new verification email.",
        )
    return user


async def require_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await get_current_user(credentials, db)


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
async def register(body: RegisterBody, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(User).where(
            (User.username == body.username) | (User.email == body.email)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already taken",
        )

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=_bcrypt.hashpw(
            body.password.encode(), _bcrypt.gensalt()
        ).decode(),
        is_verified=False,
    )
    db.add(user)
    await db.commit()
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
    verify_url = (
        f"{settings.frontend_base_url}/verify?token={verification_token}"
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
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.email == body.email))
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
async def verify(body: VerifyBody, db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(
            body.token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        if payload.get("purpose") != "verify_email":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification token",
            )
        user_id = int(payload.get("sub", 0))
    except (JWTError, ValueError, HTTPException):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
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
async def login(body: LoginBody, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.username == body.username)
    )
    user = result.scalar_one_or_none()
    if not user or not _bcrypt.checkpw(
        body.password.encode(), user.hashed_password.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Check your inbox for the verification link.",
        )

    token = _create_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "is_verified": user.is_verified,
        "is_developer": is_developer(user),
        "ai_processing_consent": user.ai_processing_consent,
        "ai_redaction_enabled": user.ai_redaction_enabled,
    }
