import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select

from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_user,
    get_request_user,
    require_user_roles,
)
from app.api.schemas import Token, UserCreate, UserLogin, UserOut
from app.core.config import settings
from app.core.rate_limit import RateLimiter
from app.core.refresh_tokens import create_refresh_token, revoke_refresh_token, rotate_refresh_token
from app.core.security import (
    create_access_token,
    get_password_hash,
    validate_password_strength,
    verify_password,
)
from app.models import User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])

_LOGIN_RATE_LIMITER = RateLimiter(max_attempts=10, window_seconds=600)
_REGISTER_RATE_LIMITER = RateLimiter(max_attempts=5, window_seconds=900)


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _get_refresh_cookie_path() -> str:
    return settings.REFRESH_TOKEN_COOKIE_PATH or f"{settings.API_STR}/auth"


def _get_refresh_cookie_secure() -> bool:
    return bool(settings.REFRESH_TOKEN_COOKIE_SECURE)


def _set_refresh_cookie(response: Response, token: str) -> None:
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_get_refresh_cookie_secure(),
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
        max_age=max_age,
        path=_get_refresh_cookie_path(),
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.REFRESH_TOKEN_COOKIE_NAME, path=_get_refresh_cookie_path())


def _determine_role(registration_token: str) -> UserRole:
    token_to_role: list[tuple[str, UserRole]] = []

    if settings.DEV_REGISTRATION_TOKEN:
        token_to_role.append((settings.DEV_REGISTRATION_TOKEN, UserRole.DEV))

    if settings.ADMIN_REGISTRATION_TOKEN:
        token_to_role.append((settings.ADMIN_REGISTRATION_TOKEN, UserRole.ADMIN))

    if settings.USER_REGISTRATION_TOKEN:
        token_to_role.append((settings.USER_REGISTRATION_TOKEN, UserRole.USER))

    for token, role in token_to_role:
        if secrets.compare_digest(registration_token, token):
            return role

    msg = "Invalid registration token"
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.post(
    "/register",
    response_model=Token,
    dependencies=[Depends(require_user_roles(get_request_user, UserRole.PUBLIC))],
)
async def register_user(
    user_data: UserCreate, session: SessionDep, request: Request, response: Response
) -> Any:
    client_host = _get_client_ip(request)
    registration_key = f"{client_host}:{user_data.email.lower()}"
    allowed, retry_after = await _REGISTER_RATE_LIMITER.hit(registration_key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    if user_data.password != user_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match"
        )

    try:
        validate_password_strength(user_data.password)
    except ValueError as exc:  # surfacing validation message to client
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    role = _determine_role(user_data.registration_token)

    # Check if user already exists
    existing_user = await session.scalar(select(User).where(User.email == user_data.email))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        name=user_data.name,
        password_hash=hashed_password,
        is_active=True,
        role=role,
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Create access token for the new user
    access_token = create_access_token(subject=str(user.id))
    refresh_token = await create_refresh_token(
        session, user.id, user_agent=request.headers.get("user-agent"), ip_address=client_host
    )
    _set_refresh_cookie(response, refresh_token)
    return Token(access_token=access_token)


@router.post(
    "/login",
    response_model=Token,
    dependencies=[Depends(require_user_roles(get_request_user, UserRole.PUBLIC))],
)
async def login_user(
    user_data: UserLogin, session: SessionDep, request: Request, response: Response
) -> Any:
    client_host = _get_client_ip(request)
    login_key = f"{client_host}:{user_data.email.lower()}"
    allowed, retry_after = await _LOGIN_RATE_LIMITER.hit(login_key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = await session.scalar(select(User).where(User.email == user_data.email))

    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=str(user.id))
    refresh_token = await create_refresh_token(
        session, user.id, user_agent=request.headers.get("user-agent"), ip_address=client_host
    )
    _set_refresh_cookie(response, refresh_token)
    return Token(access_token=access_token)


@router.post("/refresh", response_model=Token)
async def refresh_access_token(session: SessionDep, request: Request, response: Response) -> Any:
    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id, new_refresh_token = await rotate_refresh_token(
        session,
        refresh_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=_get_client_ip(request),
    )

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=str(user.id))
    _set_refresh_cookie(response, new_refresh_token)
    return Token(access_token=access_token)


@router.post("/logout")
async def logout_user(session: SessionDep, request: Request, response: Response) -> dict[str, bool]:
    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if refresh_token:
        await revoke_refresh_token(session, refresh_token)
    _clear_refresh_cookie(response)
    return {"success": True}


@router.get(
    "/me",
    response_model=UserOut,
    dependencies=[
        Depends(require_user_roles(get_current_user, UserRole.USER, UserRole.ADMIN, UserRole.DEV))
    ],
)
def get_current_user_info(current_user: CurrentUser) -> User:
    return current_user
