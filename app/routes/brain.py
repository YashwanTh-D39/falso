import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas.brain import ChatRequest
from app.services.brain import BrainService, BrainServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Brain"])
brain_service = BrainService()


@router.post("/chat")
@router.post("/chat/stream")
async def chat(request: ChatRequest):
    try:
        brain_service.validate_prompt(request.prompt)
    except BrainServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return StreamingResponse(
        brain_service.chat(request.prompt, history=request.history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
