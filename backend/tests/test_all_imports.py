import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import logging
logging.basicConfig(level=logging.INFO)

def test_imports_and_app():
    print("Testing backend modules import...")
    
    # 1. Config & Gemini
    from backend.core.config import settings
    from backend.shared.ai.gemini import (
        generate_gemini_response,
        parse_receipt_with_gemini,
        process_unified_ai_assistant_query,
        extract_steel_slots_from_prompt,
        extract_project_filters_with_gemini,
        extract_expense_filters_with_gemini,
    )
    print(f"Loaded config: Model={settings.GEMINI_MODEL}")

    # 2. Test steel slot extraction (pure rule/slot extractor)
    slots = extract_steel_slots_from_prompt("5000 sqft", "area", {})
    print(f"Steel slot extraction test: {slots}")

    # 3. Test FastAPI main app initialization
    from backend.main import app
    print(f"FastAPI app title: '{app.title}', version: '{app.version}'")

    print("ALL IMPORTS & APP INITIALIZATION SUCCESSFUL!")

if __name__ == "__main__":
    test_imports_and_app()
