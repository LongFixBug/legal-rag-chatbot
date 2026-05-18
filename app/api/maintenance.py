from fastapi import APIRouter, Depends

from app.api.documents import require_admin_token
from app.security import enforce_document_mutation_rate_limit
from app.services.registry import AppServices, get_services

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.post("/retention/purge")
async def purge_expired_data(
    _: None = Depends(require_admin_token),
    _rate_limit: None = Depends(enforce_document_mutation_rate_limit),
    services: AppServices = Depends(get_services),
) -> dict[str, int]:
    result = await services.maintenance.purge_expired_data()
    return {
        "documents_deleted": result.documents_deleted,
        "conversations_deleted": result.conversations_deleted,
    }
