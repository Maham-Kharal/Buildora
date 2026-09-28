from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.deps import get_db, require_role
from backend.db.models import User
from backend.modules.admin.ai_chat.schemas import AiChatRequest, AiChatResponse
from backend.modules.admin.ai_chat.service import handle_chat

router = APIRouter(prefix="/admin/ai", tags=["Admin - AI Operations Chat"])


@router.post("/chat", response_model=AiChatResponse)
async def chat(
    request: AiChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """
    Admin AI Chat HTTP Endpoint.
    - Validates request payload using AiChatRequest.
    - Authenticates JWT and enforces ADMIN role authorization.
    - Calls ai_chat/service.py -> orchestrator.py.
    """
    try:
        return await handle_chat(
            request=request,
            db=db,
            current_user=current_user
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Admin AI Chat error: {str(e)}"
        )
