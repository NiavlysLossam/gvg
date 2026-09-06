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


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration
cors_origins = settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["http://localhost:5173", "http://127.0.0.1:5173"]
allow_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


from fastapi.encoders import jsonable_encoder


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Ensure RFC 7807 style error responses with {'detail': ...} for validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())},
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

# Mount static files for user-uploaded assets
from fastapi.staticfiles import StaticFiles
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

# Mount API routers
app.include_router(api_router, prefix=settings.API_V1_STR)
