from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.core.database import Base, engine
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Automatically create tables if database is available
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
    yield


# Restrict interactive documentation in production environments
is_prod = (settings.ENVIRONMENT or "").strip().lower() in ("production", "prod")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=None if is_prod else f"{settings.API_V1_STR}/openapi.json",
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    lifespan=lifespan,
)

# CORS configuration
if settings.CORS_ORIGINS:
    cors_origins = [str(c).strip() for c in (settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]) if str(c).strip()]
elif not is_prod and (settings.ENVIRONMENT or "").strip().lower() in ("development", "test"):
    cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
else:
    cors_origins = []

allow_credentials = "*" not in cors_origins and len(cors_origins) > 0

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Enforce defense-in-depth HTTP security headers on all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


from fastapi.encoders import jsonable_encoder


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Ensure defense-in-depth headers on unexpected 500 internal errors."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
        headers={
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Ensure RFC 7807 style error responses with {'detail': ...} for validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())},
        headers={
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        },
    )


# Health check endpoints
@app.get("/health", tags=["system"], summary="Health Check")
@app.get(f"{settings.API_V1_STR}/health", tags=["system"], summary="API v1 Health Check")
def health_check():
    return {
        "status": "ok",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
    }


# Ensure uploads directory structure exists
upload_dir = settings.upload_dir_path
(upload_dir / "backgrounds").mkdir(parents=True, exist_ok=True)
(upload_dir / "posters").mkdir(parents=True, exist_ok=True)

# Mount static files for user-uploaded assets with strict isolation headers
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

class SecureStaticFiles(StaticFiles):
    """Serve uploaded media files with strict CSP sandbox and anti-sniffing headers."""
    def file_response(self, *args, **kwargs) -> Response:
        resp = super().file_response(*args, **kwargs)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp

app.mount("/uploads", SecureStaticFiles(directory=str(upload_dir)), name="uploads")

# Mount API routers
app.include_router(api_router, prefix=settings.API_V1_STR)

# Also mount webhooks at root /webhooks for convenience
from app.api.v1.endpoints import webhooks
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

