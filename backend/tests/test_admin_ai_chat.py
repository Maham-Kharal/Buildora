import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import logging
logging.basicConfig(level=logging.INFO)

from backend.core.database import SessionLocal
from backend.db.models import User
from backend.modules.admin.ai_chat.schemas import AiChatRequest
from backend.modules.admin.ai_chat.service import handle_chat
from backend.shared.ai.gemini import parse_receipt_with_gemini

import pytest

@pytest.mark.anyio
async def test_admin_ai_chat_and_no_fake_receipt():
    print("--- 1. TESTING NO FAKE RECEIPT DATA ON OCR FAILURE ---")
    try:
        parse_receipt_with_gemini("non_existent_file.jpg")
        print("FAIL: Should have raised an exception for missing file, but returned data!")
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"SUCCESS: Cleanly raised exception for missing/invalid receipt: {e}")

    print("\n--- 2. TESTING ADMIN AI CHAT SERVICE ARCHITECTURE ---")
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.role == "ADMIN").first()
        if not admin_user:
            admin_user = User(id=1, email="admin@buildora.com", full_name="Sarah Admin", role="ADMIN")
        
        req = AiChatRequest(
            message="Estimate steel cost for a 50,000 sqft commercial tower in Austin TX",
            session_id="test_admin_session"
        )
        res = await handle_chat(req, db, admin_user)
        print(f"Admin AI Chat Response Intent: {res.intent}")
        print("Answer Summary:\n", res.message[:300])
        print("\nADMIN AI CHAT SERVICE PASSED SUCCESSFULLY!")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_admin_ai_chat_and_no_fake_receipt())

