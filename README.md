# Phase 2 Todo Backend

FastAPI backend for the Full-Stack Todo Web Application with authentication and task management.

## Setup

1. Install dependencies:
```bash
uv sync
```

2. Set environment variables in `/env/.env`:
```
DATABASE_URL=postgresql://...
BETTER_AUTH_SECRET=your-secret-key
```

3. Run migrations:
```bash
uv run alembic upgrade head
```

4. Start server:
```bash
uv run uvicorn src.main:app --reload
```

API documentation available at: http://localhost:8000/docs
