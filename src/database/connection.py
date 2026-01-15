"""Database connection module using asyncpg with connection pooling for Neon PostgreSQL."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
import os
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), "../../../env/.env")
load_dotenv(env_path)

# Get DATABASE_URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

# Convert postgresql:// to postgresql+asyncpg:// for async driver
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("psql"):
    # Handle the psql format from env file
    DATABASE_URL = DATABASE_URL.replace("psql 'postgresql://", "postgresql+asyncpg://").rstrip("'")

# Create async engine with asyncpg driver
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging during development
    poolclass=NullPool,  # Use NullPool for serverless databases like Neon
    future=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncSession:
    """
    Dependency for FastAPI to get database session.

    Usage:
        @app.get("/")
        async def read_root(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables (for development/testing)."""
    from sqlmodel import SQLModel

    async with engine.begin() as conn:
        # Import all models here to ensure they're registered
        # from src.models.user import User
        # from src.models.task import Task
        await conn.run_sync(SQLModel.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
