from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.legal import router as legal_router
from app.config import get_settings
from app.services.registry import build_services

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    services = await build_services()
    app.state.services = services
    if services.settings.preload_sample_data and not await services.documents.list_documents():
        await services.documents.ingest_directory(services.settings.data_dir)
    yield
    await services.close()


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.include_router(chat_router, prefix=settings.api_prefix)
app.include_router(documents_router, prefix=settings.api_prefix)
app.include_router(legal_router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": settings.app_name, "docs": "/docs"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}
