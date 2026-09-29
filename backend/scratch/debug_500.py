import asyncio
from backend.core.database import SessionLocal
from backend.modules.admin.ai_chat.orchestrator import orchestrator
from backend.db.models import User

async def main():
    db = SessionLocal()
    admin = db.query(User).filter(User.role == "ADMIN").first()
    try:
        res = await orchestrator.orchestrate(
            message="I want to estimate steel",
            session_id="debug_session_1",
            db=db,
            current_user=admin
        )
        print("SUCCESS:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        db.close()

asyncio.run(main())
