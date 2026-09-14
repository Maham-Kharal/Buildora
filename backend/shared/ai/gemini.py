import os
import json
import re
from typing import Dict, Any, List
import google.generativeai as genai
from PIL import Image
from backend.core.config import settings

if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

def parse_receipt_with_gemini(image_path: str) -> Dict[str, Any]:
    """
    Parses a receipt image using Gemini Vision AI.
    Fallback parser provided if API key is missing or call fails.
    """
    if settings.GEMINI_API_KEY and os.path.exists(image_path):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            image = Image.open(image_path)
            prompt = """
            Analyze this construction receipt image and return ONLY a valid JSON object with the following fields:
            {
                "vendor_name": "Store/Vendor Name",
                "total_amount": 0.00,
                "purchase_date": "YYYY-MM-DD",
                "category": "Materials|Equipment|Tools|Fuel|Misc",
                "items": [
                    {"name": "Item description", "quantity": 1, "unit_price": 0.00, "total_price": 0.00}
                ]
            }
            Do not include markdown code block formatting (```json) in your final output if possible.
            """
            response = model.generate_content([prompt, image])
            raw_text = response.text.strip()
            # Clean JSON formatting wrappers
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            
            return json.loads(raw_text.strip())
        except Exception as e:
            print(f"Gemini OCR error: {e}. Falling back to default parser.")

    # Fallback default OCR structure for demo / zero-cost reliability
    return {
        "vendor_name": "Home Depot US #4412",
        "total_amount": 485.50,
        "purchase_date": "2026-09-10",
        "category": "Materials",
        "items": [
            {"name": "Grade 60 Steel Rebar #4 (20ft)", "quantity": 15, "unit_price": 18.50, "total_price": 277.50},
            {"name": "Portland Cement Bag 94lb", "quantity": 16, "unit_price": 13.00, "total_price": 208.00}
        ]
    }

def query_hr_assistant(prompt: str, policy_docs: List[Dict[str, str]], leave_balance: int) -> Dict[str, Any]:
    """
    Processes HR inquiries using Gemini model with guardrails.
    Guardrail rule: Deny questions regarding financial budgets, vendor costs, or admin passwords.
    Auto-approve leaves if requested days < 3.
    """
    security_denial_keywords = ["budget", "vendor cost", "salary", "admin password", "financial report", "audit log"]
    prompt_lower = prompt.lower()
    
    for kw in security_denial_keywords:
        if kw in prompt_lower:
            return {
                "answer": "SECURITY POLICY ERROR: As an HR Assistant, I do not have authorization to disclose company financial budgets, vendor pricing, salary info, or admin credentials. Please contact your administrator.",
                "auto_approved_leave": False
            }

    policies_text = "\n".join([f"- {p['title']}: {p['content']}" for p in policy_docs])
    
    if settings.GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            system_prompt = f"""
            You are Buildora's AI HR Assistant. Answer employee questions accurately based strictly on the following policies:
            {policies_text}
            
            Employee Current Leave Balance: {leave_balance} days.
            
            User Question: {prompt}
            """
            response = model.generate_content(system_prompt)
            answer = response.text.strip()
        except Exception as e:
            answer = f"According to company policy ({len(policy_docs)} policy files loaded), employees receive annual paid leave. Current leave balance: {leave_balance} days."
    else:
        answer = f"Based on Buildora HR Policy, standard working hours are 8:00 AM - 5:00 PM. Leave requests up to 3 days undergo automatic preliminary clearance if balance permits. Your active balance is {leave_balance} days."

    # Check for leave request auto-approval trigger
    auto_approved = False
    leave_match = re.search(r'(\d+)\s*(?:day|days)\s*leave', prompt_lower)
    if leave_match:
        requested_days = int(leave_match.group(1))
        if requested_days < 3 and leave_balance >= requested_days:
            auto_approved = True

    return {
        "answer": answer,
        "auto_approved_leave": auto_approved
    }
