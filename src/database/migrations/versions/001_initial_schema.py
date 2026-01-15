"""Initial schema: users and tasks tables with indexes and triggers

Revision ID: 001
Revises:
Create Date: 2026-01-12 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create users and tasks tables with indexes and update trigger."""

    # Create users table
    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(254) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    # Create unique index on email
    op.execute("CREATE UNIQUE INDEX idx_users_email ON users(email)")

    # Create tasks table
    op.execute("""
        CREATE TABLE tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(100) NOT NULL,
            description VARCHAR(500),
            completed BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    # Create indexes for efficient queries
    op.execute("CREATE INDEX idx_tasks_user_id ON tasks(user_id)")
    op.execute("CREATE INDEX idx_tasks_user_created ON tasks(user_id, created_at DESC)")

    # Create trigger function to auto-update updated_at timestamp
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql'
    """)

    # Create trigger on tasks table
    op.execute("""
        CREATE TRIGGER update_tasks_updated_at
        BEFORE UPDATE ON tasks
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()
    """)


def downgrade() -> None:
    """Drop all tables, indexes, and triggers (rollback migration)."""

    # Drop trigger first
    op.execute("DROP TRIGGER IF EXISTS update_tasks_updated_at ON tasks")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")

    # Drop indexes (will be dropped automatically with tables, but explicit for clarity)
    op.execute("DROP INDEX IF EXISTS idx_tasks_user_created")
    op.execute("DROP INDEX IF EXISTS idx_tasks_user_id")
    op.execute("DROP INDEX IF EXISTS idx_users_email")

    # Drop tables (CASCADE handles foreign key constraints)
    op.execute("DROP TABLE IF EXISTS tasks CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
