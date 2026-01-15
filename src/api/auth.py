"""Authentication API endpoints (register, login, logout)."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.auth import RegisterRequest, LoginRequest, AuthResponse, RegisterResponse
from src.services.user_service import UserService
from src.services.auth_service import AuthService
from src.database.connection import get_session
from src.middleware.auth import get_current_user
from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=RegisterResponse)
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> RegisterResponse:
    """
    Register a new user with email and password.

    Args:
        request: Registration request with email and password
        session: Database session (injected)

    Returns:
        RegisterResponse with success message and user_id

    Raises:
        400: Validation error (invalid email format, weak password)
        409: Email already registered
    """
    logger.info("registration_attempt", email=request.email)

    response = await UserService.register_user(session, request)

    return response


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    """
    Login user and set JWT in httpOnly cookie.

    Args:
        request: Login request with email and password
        response: FastAPI Response object to set cookie
        session: Database session (injected)

    Returns:
        AuthResponse with success message and user info

    Raises:
        401: Invalid email or password
    """
    logger.info("login_attempt", email=request.email)

    # Authenticate and get token
    token, user = await AuthService.login(session, request)

    # Set JWT in httpOnly cookie
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        max_age=settings.COOKIE_MAX_AGE,
        httponly=settings.COOKIE_HTTP_ONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAME_SITE,
        path="/",
    )

    return AuthResponse(
        message="Login successful",
        user=user,
    )


@router.get("/me", response_model=AuthResponse)
async def get_current_user_info(
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
) -> AuthResponse:
    """
    Get current authenticated user information from JWT cookie.

    Args:
        session: Database session (injected)
        user: Verified token payload from JWT cookie (injected)

    Returns:
        AuthResponse with user info

    Raises:
        401: Not authenticated or invalid token
        404: User not found in database
    """
    from fastapi import HTTPException
    from src.middleware.auth import get_user_id
    from src.services.user_service import UserService

    user_id = get_user_id(user)
    db_user = await UserService.get_user_by_id(session, user_id)

    if not db_user:
        logger.warn("user_not_found", user_id=str(user_id))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return AuthResponse(
        message="Authenticated",
        user={"id": str(db_user.id), "email": db_user.email},
    )


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """
    Logout user by clearing JWT cookie.

    Args:
        response: FastAPI Response object to clear cookie

    Returns:
        Success message
    """
    logger.info("logout_request")

    # Clear JWT cookie by setting Max-Age=0
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value="",
        max_age=0,
        httponly=settings.COOKIE_HTTP_ONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAME_SITE,
        path="/",
    )

    return {"message": "Logout successful"}
