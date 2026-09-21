import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import logging
logging.basicConfig(level=logging.INFO)

from backend.shared.ai.gemini import (
    process_unified_ai_assistant_query,
    parse_receipt_with_gemini,
)
from backend.core.database import SessionLocal

def test_features():
    print("--- TESTING GEMINI HR ASSISTANT FEATURE ---")
    db = SessionLocal()
    try:
        res = process_unified_ai_assistant_query(
            prompt="What is the company safety policy for construction sites?",
            db=db,
            user_role="WORKER",
            session_id="test_sess"
        )
        print("HR Assistant Answer:\n", res.get("answer"))
    finally:
        db.close()

if __name__ == "__main__":
    test_features()
