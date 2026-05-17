from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.schemas.document import DocumentIngestRequest, DocumentIngestResponse, DocumentResponse
from app.services.registry import AppServices, get_services

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentResponse])
async def list_documents(services: AppServices = Depends(get_services)) -> list[DocumentResponse]:
    documents = await services.documents.list_documents()
    return [DocumentResponse(**document.to_dict()) for document in documents]


@router.post("/ingest", response_model=DocumentIngestResponse)
async def ingest_document(
    request: DocumentIngestRequest,
    services: AppServices = Depends(get_services),
) -> DocumentIngestResponse:
    document, chunks = await services.documents.ingest_document(request)
    return DocumentIngestResponse(document=DocumentResponse(**document.to_dict()), chunks_indexed=chunks)


@router.post("/upload", response_model=DocumentIngestResponse)
async def upload_document(
    title: str = Form(...),
    file: UploadFile = File(...),
    services: AppServices = Depends(get_services),
) -> DocumentIngestResponse:
    try:
        document, chunks = await services.documents.ingest_uploaded_file(
            title=title,
            filename=file.filename or "upload.txt",
            content=await file.read(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DocumentIngestResponse(document=DocumentResponse(**document.to_dict()), chunks_indexed=chunks)


@router.post("/preload")
async def preload_documents(services: AppServices = Depends(get_services)) -> dict[str, int]:
    count = await services.documents.ingest_directory(
        services.settings.data_dir,
        include_pattern=services.settings.preload_include_pattern,
    )
    return {"documents_ingested": count}


@router.post("/reindex")
async def reindex_documents(services: AppServices = Depends(get_services)) -> dict[str, int]:
    deleted, ingested = await services.documents.reindex_directory(
        services.settings.data_dir,
        include_pattern=services.settings.preload_include_pattern,
    )
    return {"documents_deleted": deleted, "documents_ingested": ingested}


@router.delete("/{document_id}")
async def delete_document(document_id: str, services: AppServices = Depends(get_services)) -> dict[str, bool]:
    deleted = await services.documents.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True}
