from fastapi import APIRouter, Depends, Query

from app.schemas.legal import LegalSearchResponse
from app.services.registry import AppServices, get_services

router = APIRouter(prefix="/legal", tags=["legal"])


@router.get("/search", response_model=LegalSearchResponse)
async def legal_search(
    q: str = Query(..., min_length=2),
    article: str | None = Query(default=None),
    top_k: int | None = Query(default=None, ge=1, le=10),
    services: AppServices = Depends(get_services),
) -> LegalSearchResponse:
    return await services.rag.legal_search(query=q, article_filter=article, top_k=top_k)
