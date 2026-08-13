import asyncio
import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas.brain import ChatRequest
from app.services.brain import BrainService, BrainServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Brain"])
brain_service = BrainService()


@router.post("/chat/warmup")
async def chat_warmup():
    """Fire-and-forget Ollama warm: pre-loads the model so the first chat
    message streams back instantly instead of paying the model-load cost."""
    provider = brain_service.provider
    from config.settings import settings
    if settings.ai_provider != "ollama" or not hasattr(provider, "warm"):
        return {"status": "noop"}

    async def _warm():
        await provider.warm()

    asyncio.create_task(_warm())
    return {"status": "warming"}


@router.post("/chat")
@router.post("/chat/stream")
async def chat(request: ChatRequest):
    try:
        prompt_str = request.get_prompt()
        brain_service.validate_prompt(prompt_str)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return StreamingResponse(
        brain_service.chat(prompt_str, history=request.history, request_id=request.request_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
