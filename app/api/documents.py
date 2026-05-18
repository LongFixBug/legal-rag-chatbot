from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status

from app.schemas.document import DocumentIngestRequest, DocumentIngestResponse, DocumentResponse
from app.security import enforce_document_mutation_rate_limit
from app.services.registry import AppServices, get_services

router = APIRouter(prefix="/documents", tags=["documents"])


async def require_admin_token(
    x_admin_token: str | None = Header(default=None),
    services: AppServices = Depends(get_services),
) -> None:
    expected = services.settings.admin_token.strip()
    if expected and x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Admin token required")


@router.get("", response_model=list[DocumentResponse])
async def list_documents(services: AppServices = Depends(get_services)) -> list[DocumentResponse]:
    documents = await services.documents.list_documents()
    return [DocumentResponse(**document.to_dict()) for document in documents]


@router.post("/ingest", response_model=DocumentIngestResponse)
async def ingest_document(
    request: DocumentIngestRequest,
    _: None = Depends(require_admin_token),
    _rate_limit: None = Depends(enforce_document_mutation_rate_limit),
    services: AppServices = Depends(get_services),
) -> DocumentIngestResponse:
    document, chunks = await services.documents.ingest_document(request)
    return DocumentIngestResponse(document=DocumentResponse(**document.to_dict()), chunks_indexed=chunks)


@router.post("/upload", response_model=DocumentIngestResponse)
async def upload_document(
    title: str = Form(...),
    file: UploadFile = File(...),
    _: None = Depends(require_admin_token),
    _rate_limit: None = Depends(enforce_document_mutation_rate_limit),
    services: AppServices = Depends(get_services),
) -> DocumentIngestResponse:
    _validate_upload_file_metadata(file, services)
    content = await file.read()
    if len(content) > services.settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File too large. Maximum upload size is {services.settings.max_upload_bytes} bytes.",
        )
    try:
        document, chunks = await services.documents.ingest_uploaded_file(
            title=title,
            filename=file.filename or "upload.txt",
            content=content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DocumentIngestResponse(document=DocumentResponse(**document.to_dict()), chunks_indexed=chunks)


@router.post("/preload")
async def preload_documents(
    _: None = Depends(require_admin_token),
    _rate_limit: None = Depends(enforce_document_mutation_rate_limit),
    services: AppServices = Depends(get_services),
) -> dict[str, int]:
    count = await services.documents.ingest_directory(
        services.settings.data_dir,
        include_pattern=services.settings.preload_include_pattern,
    )
    return {"documents_ingested": count}


@router.post("/reindex")
async def reindex_documents(
    _: None = Depends(require_admin_token),
    _rate_limit: None = Depends(enforce_document_mutation_rate_limit),
    services: AppServices = Depends(get_services),
) -> dict[str, int]:
    deleted, ingested = await services.documents.reindex_directory(
        services.settings.data_dir,
        include_pattern=services.settings.preload_include_pattern,
    )
    return {"documents_deleted": deleted, "documents_ingested": ingested}


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    _: None = Depends(require_admin_token),
    _rate_limit: None = Depends(enforce_document_mutation_rate_limit),
    services: AppServices = Depends(get_services),
) -> dict[str, bool]:
    deleted = await services.documents.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True}


def _csv_to_set(value: str) -> set[str]:
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def _validate_upload_file_metadata(file: UploadFile, services: AppServices) -> None:
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    allowed_extensions = _csv_to_set(services.settings.allowed_upload_extensions)
    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {extension or 'unknown'}",
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    allowed_mime_types = _csv_to_set(services.settings.allowed_upload_mime_types)
    if content_type and content_type not in allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {content_type}",
        )
