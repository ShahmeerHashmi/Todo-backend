"""Pytest fixtures and configuration for backend tests."""

import asyncio
import os
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlmodel import SQLModel

# Set test environment
os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-for-jwt-signing"
os.environ["GROQ_API_KEY"] = "test-api-key"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        # Import models to ensure they're registered
        from src.models.user import User
        from src.models.task import Task
        from src.models.conversation import Conversation
        from src.models.message import Message

        await conn.run_sync(SQLModel.metadata.create_all)

    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def test_user_id() -> str:
    """Generate a test user UUID."""
    return str(uuid4())


@pytest_asyncio.fixture
async def test_user(async_session: AsyncSession) -> dict:
    """Create a test user in the database."""
    from src.models.user import User
    from uuid import uuid4

    user_id = uuid4()
    user = User(
        id=user_id,
        email=f"test-{user_id}@example.com",
        password_hash="hashed_password",
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    return {"user_id": str(user.id), "email": user.email}
