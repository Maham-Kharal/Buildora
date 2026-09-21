import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import logging
logging.basicConfig(level=logging.INFO)

from backend.core.config import settings
from backend.shared.ai.gemini import generate_gemini_response

def test_gemini_smoke():
    print(f"--- BUILDORA GEMINI SMOKE TEST ---")
    print(f"Target Model: {settings.GEMINI_MODEL}")
    if not settings.GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY is missing or empty.")
        sys.exit(1)

    prompt = "Reply with exactly: BUILDORA_GEMINI_OK"
    try:
        response_text = generate_gemini_response(contents=prompt)
        print(f"Raw Gemini Response: '{response_text}'")
        if "BUILDORA_GEMINI_OK" in response_text:
            print("SUCCESS: Real Gemini API call succeeded and returned expected response!")
            return 0
        else:
            print(f"WARNING: Unexpected response payload: '{response_text}'")
            return 1
    except Exception as e:
        print(f"ERROR: Gemini API call failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(test_gemini_smoke())
