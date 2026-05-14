from fastapi import APIRouter, Depends, HTTPException

from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationHistoryMessageResponse,
    ConversationResponse,
    CreateConversationRequest,
)
from app.services.registry import AppServices, get_services

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/query", response_model=ChatResponse)
async def query_chat(request: ChatRequest, services: AppServices = Depends(get_services)) -> ChatResponse:
    return await services.rag.chat(request.question, top_k=request.top_k, conversation_id=request.conversation_id)


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(services: AppServices = Depends(get_services)) -> list[ConversationResponse]:
    conversations = await services.rag.list_conversations()
    return [ConversationResponse(**conversation.to_dict()) for conversation in conversations]


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: CreateConversationRequest,
    services: AppServices = Depends(get_services),
) -> ConversationResponse:
    conversation = await services.rag.create_conversation(title=request.title)
    return ConversationResponse(**conversation.to_dict())


@router.get("/conversations/{conversation_id}", response_model=list[ConversationHistoryMessageResponse])
async def get_conversation_history(
    conversation_id: str,
    services: AppServices = Depends(get_services),
) -> list[ConversationHistoryMessageResponse]:
    history = await services.rag.get_conversation_history(conversation_id)
    if history is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [ConversationHistoryMessageResponse(**message.to_dict()) for message in history]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, services: AppServices = Depends(get_services)) -> dict[str, bool]:
    deleted = await services.rag.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True}
