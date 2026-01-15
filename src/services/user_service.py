"""User service for registration and user management."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import bcrypt
import re
from uuid import UUID

from src.models.user import User
from src.models.auth import RegisterRequest, RegisterResponse
from src.api.errors import raise_duplicate_email_error, raise_validation_error
from src.config.logging import get_logger

logger = get_logger(__name__)


class UserService:
    """Service for user registration and management operations."""

    @staticmethod
    def validate_email(email: str) -> None:
        """
        Validate email format.

        Args:
            email: Email address to validate

        Raises:
            ValidationError: If email format is invalid
        """
        # Basic email validation (Pydantic EmailStr already validates, this is defense-in-depth)
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise_validation_error("email", "Invalid email format")

    @staticmethod
    def validate_password(password: str) -> None:
        """
        Validate password strength.

        Args:
            password: Password to validate

        Raises:
            ValidationError: If password does not meet requirements (minimum 8 characters)
        """
        if len(password) < 8:
            raise_validation_error("password", "Password must be at least 8 characters long")

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Bcrypt hashed password
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    @staticmethod
    async def check_email_exists(session: AsyncSession, email: str) -> bool:
        """
        Check if email already exists in database.

        Args:
            session: Database session
            email: Email address to check

        Returns:
            True if email exists, False otherwise
        """
        statement = select(User).where(User.email == email)
        result = await session.execute(statement)
        user = result.scalar_one_or_none()
        return user is not None

    @staticmethod
    async def register_user(
        session: AsyncSession,
        request: RegisterRequest
    ) -> RegisterResponse:
        """
        Register a new user with email and password.

        Args:
            session: Database session
            request: Registration request with email and password

        Returns:
            RegisterResponse with success message and user_id

        Raises:
            ValidationError: If email format or password strength is invalid
            ConflictError: If email is already registered (409)
        """
        # Validate email format
        UserService.validate_email(request.email)

        # Validate password strength
        UserService.validate_password(request.password)

        # Check for duplicate email
        email_exists = await UserService.check_email_exists(session, request.email)
        if email_exists:
            logger.warn("registration_failed_duplicate_email", email=request.email)
            raise_duplicate_email_error(request.email)

        # Hash password
        password_hash = UserService.hash_password(request.password)

        # Create user
        user = User(
            email=request.email,
            password_hash=password_hash,
        )

        session.add(user)
        await session.commit()
        await session.refresh(user)

        logger.info("user_registered", user_id=str(user.id), email=user.email)

        return RegisterResponse(
            message="User registered successfully",
            user_id=user.id,
        )

    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
        """
        Get user by ID.

        Args:
            session: Database session
            user_id: User's UUID

        Returns:
            User if found, None otherwise
        """
        statement = select(User).where(User.id == user_id)
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
        """
        Get user by email address.

        Args:
            session: Database session
            email: User's email address

        Returns:
            User if found, None otherwise
        """
        statement = select(User).where(User.email == email)
        result = await session.execute(statement)
        return result.scalar_one_or_none()
