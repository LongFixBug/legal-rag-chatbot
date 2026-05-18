from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status

from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.legal import router as legal_router
from app.api.maintenance import router as maintenance_router
from app.config import get_settings
from app.observability import InMemoryMetrics, configure_logging, get_metrics, observability_middleware
from app.services.rate_limit import FixedWindowRateLimiter
from app.services.registry import build_services

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    services = await build_services()
    app.state.services = services
    app.state.rate_limiter = FixedWindowRateLimiter()
    app.state.metrics = InMemoryMetrics()
    if services.settings.preload_sample_data and not await services.documents.list_documents():
        await services.documents.ingest_directory(
            services.settings.data_dir,
            include_pattern=services.settings.preload_include_pattern,
        )
    yield
    await services.close()


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.middleware("http")(observability_middleware)
app.include_router(chat_router, prefix=settings.api_prefix)
app.include_router(documents_router, prefix=settings.api_prefix)
app.include_router(legal_router, prefix=settings.api_prefix)
app.include_router(maintenance_router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": settings.app_name, "docs": "/docs"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}


@app.get("/health/ready")
async def health_ready(request: Request, response: Response) -> dict[str, object]:
    checks = await request.app.state.services.readiness_summary()
    ready = all(bool(item.get("operational", item.get("ready"))) for item in checks.values())
    degraded = any(not bool(item.get("ready")) for item in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if ready and not degraded else "degraded",
        "version": settings.app_version,
        "ready": ready,
        "checks": checks,
    }


@app.get("/health/metrics")
async def health_metrics(request: Request) -> dict[str, object]:
    return get_metrics(request).snapshot()
