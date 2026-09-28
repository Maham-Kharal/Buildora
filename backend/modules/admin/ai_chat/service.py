import logging
from sqlalchemy.orm import Session

from backend.db.models import User
from backend.modules.admin.ai_chat.schemas import AiChatRequest, AiChatResponse
from backend.modules.admin.ai_chat.orchestrator import orchestrator

logger = logging.getLogger("buildora.ai_chat.service")


async def handle_chat(
    request: AiChatRequest,
    db: Session,
    current_user: User
) -> AiChatResponse:
    """
    Feature entry service for Admin AI Chat.
    - Loads/initializes conversation session.
    - Delegates to backend orchestrator (BuildoraOrchestrator).
    - Returns structured AiChatResponse.
    """
    session_id = request.session_id or "default_admin_session"
    
    # Execute backend orchestrator
    result = await orchestrator.orchestrate(
        message=request.message,
        session_id=session_id,
        db=db,
        current_user=current_user
    )

    return AiChatResponse(
        session_id=result["session_id"],
        message=result["message"],
        intent=result["intent"],
        agent=result["agent"],
        status=result["status"],
        data=result.get("data")
    )
