"""Authentication service for login and JWT token management."""

from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt

from src.models.auth import LoginRequest, AuthResponse, UserResponse
from src.services.user_service import UserService
from src.middleware.auth import create_token
from src.api.errors import raise_invalid_credentials_error
from src.config.logging import get_logger

logger = get_logger(__name__)


class AuthService:
    """Service for authentication operations (login, token generation)."""

    @staticmethod
    def verify_password(plain_password: str, password_hash: str) -> bool:
        """
        Verify plain password against hashed password.

        Args:
            plain_password: Plain text password from user
            password_hash: Bcrypt hashed password from database

        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                password_hash.encode('utf-8')
            )
        except Exception as e:
            logger.error("password_verification_error", error=str(e))
            return False

    @staticmethod
    async def login(
        session: AsyncSession,
        request: LoginRequest
    ) -> tuple[str, UserResponse]:
        """
        Authenticate user and generate JWT token.

        Args:
            session: Database session
            request: Login request with email and password

        Returns:
            Tuple of (JWT token string, UserResponse)

        Raises:
            UnauthorizedError: If email not found or password incorrect (401)
        """
        # Get user by email
        user = await UserService.get_user_by_email(session, request.email)

        if not user:
            logger.warn("login_failed_user_not_found", email=request.email)
            raise_invalid_credentials_error()

        # Verify password
        password_valid = AuthService.verify_password(request.password, user.password_hash)

        if not password_valid:
            logger.warn("login_failed_invalid_password", email=request.email, user_id=str(user.id))
            raise_invalid_credentials_error()

        # Generate JWT token
        token = create_token(user.id, user.email)

        logger.info("user_logged_in", user_id=str(user.id), email=user.email)

        # Create user response
        user_response = UserResponse(
            id=user.id,
            email=user.email,
        )

        return token, user_response
