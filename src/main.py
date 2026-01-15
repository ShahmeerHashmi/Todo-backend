"""FastAPI application entry point with CORS, logging, and error handlers."""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
import time
from typing import Any

from src.config.settings import settings
from src.config.logging import setup_logging, get_logger, bind_context, clear_context

# Setup structured logging
setup_logging()
logger = get_logger(__name__)

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Multi-user Todo application backend with JWT authentication",
    debug=settings.DEBUG,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Short-circuit OPTIONS preflight requests early to avoid any redirect
# or auth middleware interference. This will return a 204 and echo
# the request origin when allowed by `settings.CORS_ORIGINS`.
@app.middleware("http")
async def options_preflight_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        origin = request.headers.get("origin")
        allowed = settings.CORS_ORIGINS or []

        # Determine Access-Control-Allow-Origin value
        if origin and ("*" in allowed or origin in allowed):
            ac_allow_origin = origin
        elif "*" in allowed:
            ac_allow_origin = "*"
        else:
            # No matching origin; still respond with 204 without ACAO
            ac_allow_origin = None

        headers = {
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
            "Access-Control-Allow-Headers": "Authorization,Content-Type,Accept",
            "Access-Control-Allow-Credentials": "true",
        }
        if ac_allow_origin:
            headers["Access-Control-Allow-Origin"] = ac_allow_origin

        return Response(status_code=204, headers=headers)



# Logging Middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next: Any) -> Any:
    """Log all HTTP requests with structured logging and request context."""
    # Generate request ID
    import uuid
    request_id = str(uuid.uuid4())

    # Bind request context for logging
    bind_context(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    # Log request
    start_time = time.time()
    logger.info(
        "request_started",
        method=request.method,
        path=str(request.url.path),
        request_id=request_id,
    )

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration = time.time() - start_time

    # Log response
    logger.info(
        "request_completed",
        method=request.method,
        path=str(request.url.path),
        status_code=response.status_code,
        duration_ms=round(duration * 1000, 2),
        request_id=request_id,
    )

    # Clear context
    clear_context()

    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id

    return response


# Global Exception Handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors with standardized Error schema."""
    from datetime import datetime

    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"][1:])  # Skip 'body' prefix
        errors.append({
            "field": field,
            "message": error["msg"],
        })

    logger.warn(
        "validation_error",
        path=str(request.url.path),
        errors=errors,
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "message": "Validation failed",
            "errors": errors,
            "statusCode": 400,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with standardized Error schema."""
    from datetime import datetime

    logger.error(
        "unexpected_error",
        path=str(request.url.path),
        error=str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "message": "Internal server error",
            "errors": [],
            "statusCode": 500,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    )


# Health Check Endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "version": settings.APP_VERSION}


# Startup Event
@app.on_event("startup")
async def startup_event() -> None:
    """Execute on application startup."""
    logger.info("application_startup", app_name=settings.APP_NAME, version=settings.APP_VERSION)


# Shutdown Event
@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Execute on application shutdown."""
    logger.info("application_shutdown", app_name=settings.APP_NAME)

    # Close database connections
    from src.database.connection import close_db
    await close_db()


# Import and include routers
from src.api.auth import router as auth_router
from src.api.tasks import router as tasks_router
from src.api.chat import router as chat_router

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(tasks_router, prefix="/tasks", tags=["Tasks"])
app.include_router(chat_router, prefix="/chat", tags=["Chat"])
