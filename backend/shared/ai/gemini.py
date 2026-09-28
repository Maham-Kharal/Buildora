import os
import json
import re
import datetime
import logging
import time
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types
from PIL import Image
from backend.core.config import settings
from backend.shared.ai.session_manager import session_manager
from backend.shared.ai.tavily import get_market_steel_price
from backend.shared.ai.tools import (
    query_financial_expenses_db,
    query_historical_projects_db,
    query_leave_balance_db,
    query_company_policy_kb,
    parse_date_range_from_prompt,
)

logger = logging.getLogger("buildora.gemini")

# -----------------------------------------------------------------------
# CENTRALIZED GEMINI CLIENT & GENERATION HELPER
# -----------------------------------------------------------------------
_gemini_client: Optional[genai.Client] = None

def get_gemini_client() -> Optional[genai.Client]:
    """Lazy-initializes and returns a reusable Google GenAI Client instance."""
    global _gemini_client
    if not settings.GEMINI_API_KEY:
        logger.warning("Gemini request skipped: GEMINI_API_KEY is not configured.")
        return None
    if _gemini_client is None:
        try:
            _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
            logger.info("Initialized central Gemini Client.")
        except Exception as e:
            logger.error(f"Failed to initialize central Gemini client: {e}")
            return None
    return _gemini_client

def generate_gemini_response(
    contents: Any,
    system_instruction: Optional[str] = None,
    model: Optional[str] = None,
    max_retries: int = 3
) -> str:
    """
    Centralized generation helper using the current google-genai Python SDK.
    Handles logging, error reporting, model selection, and automatic retries for transient 503 errors.
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("Gemini API call skipped: GEMINI_API_KEY is missing.")
        raise ValueError("GEMINI_API_KEY is missing or empty.")

    client = get_gemini_client()
    if not client:
        raise ValueError("Gemini client could not be initialized.")

    target_model = model or settings.GEMINI_MODEL
    logger.info(f"Gemini request started using model='{target_model}'")

    config = None
    if system_instruction:
        config = types.GenerateContentConfig(system_instruction=system_instruction)

    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )

            if not response or not response.text:
                logger.error(f"Gemini request failed: Empty response from model '{target_model}'.")
                raise ValueError(f"Gemini returned an empty response for model '{target_model}'.")

            logger.info(f"Gemini request completed successfully using model='{target_model}'.")
            return response.text.strip()
        except Exception as e:
            last_exception = e
            err_msg = str(e).lower()
            if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg or "rate limit" in err_msg:
                logger.warning(f"Gemini quota/rate limit exhausted (429): {e}. Aborting retries immediately.")
                raise e
            logger.warning(f"Gemini request attempt {attempt}/{max_retries} failed using model='{target_model}': {e}")
            if attempt < max_retries:
                time.sleep(1.0 * attempt)

    logger.error(f"Gemini request failed after {max_retries} attempts using model='{target_model}': {last_exception}", exc_info=True)
    raise last_exception

def generate_embeddings(
    texts: List[str],
    model: Optional[str] = None,
    output_dimensionality: Optional[int] = None
) -> List[List[float]]:
    """
    Generates embedding vectors for a list of text strings using the centralized Google GenAI client.
    Uses the configured embedding model ('gemini-embedding-2') and output dimensionality (768).
    Preserves input/output ordering and validates vector counts.
    """
    if not texts:
        return []

    if not settings.GEMINI_API_KEY:
        logger.warning("Gemini embedding request skipped: GEMINI_API_KEY is missing.")
        raise ValueError("GEMINI_API_KEY is missing or empty.")

    client = get_gemini_client()
    if not client:
        raise ValueError("Gemini client could not be initialized.")

    target_model = model or settings.GEMINI_EMBEDDING_MODEL
    target_dim = output_dimensionality or settings.GEMINI_EMBEDDING_DIMENSION

    logger.info(f"Generating embeddings for {len(texts)} chunks using model='{target_model}', dim={target_dim}")

    config = types.EmbedContentConfig(output_dimensionality=target_dim)

    try:
        embeddings: List[List[float]] = []
        batch_size = 50
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            response = client.models.embed_content(
                model=target_model,
                contents=batch_texts,
                config=config
            )

            if not response or not response.embeddings:
                raise ValueError(f"Gemini returned empty embeddings for model '{target_model}'.")

            for emb in response.embeddings:
                vec = list(emb.values)
                if target_dim and len(vec) != target_dim:
                    logger.warning(f"Embedding dimension mismatch: expected {target_dim}, got {len(vec)}")
                embeddings.append(vec)

        if len(embeddings) != len(texts):
            raise ValueError(f"Embedding count mismatch: expected {len(texts)}, got {len(embeddings)}")

        return embeddings
    except Exception as e:
        logger.error(f"Failed to generate embeddings using model '{target_model}': {e}", exc_info=True)
        raise e

# -----------------------------------------------------------------------
# INTENT CLASSIFICATION & AGENT RESULT FORMATTING HELPERS
# -----------------------------------------------------------------------

def classify_intent_with_gemini(message: str) -> str:
    """
    Uses Gemini NLP to classify natural language prompt into a supported intent string.
    Returns one of: 'steel_estimation', 'financial_report', 'project_history', 'company_policy', 'general_conversation'.
    """
    if not settings.GEMINI_API_KEY:
        m = message.lower()
        if any(k in m for k in ["steel", "takeoff", "rebar"]): return "steel_estimation"
        if any(k in m for k in ["past project", "historical", "previous project", "past projects"]): return "project_history"
        if any(k in m for k in ["expense", "spend", "spent", "spending", "financial", "budget", "cost"]): return "financial_report"
        if any(k in m for k in ["policy", "rule", "safety", "protocol", "guideline"]): return "company_policy"
        if any(k in m for k in ["sqft", "sq.ft", "square feet", "footing", "moment frame"]): return "steel_estimation"
        return "general_conversation"

    try:
        sys_p = f"""
        You are a Natural Language Intent Classifier for the Buildora Construction Console.
        Analyze the user's message and determine their intent.
        
        User Message: "{message}"
        
        You MUST choose exactly ONE of the following 5 supported intent labels:
        - "steel_estimation": User is asking to calculate, estimate, or discuss steel takeoff, rebar quantities, building area sqft, foundation type, floors, structural design, or steel cost/budget estimation.
        - "financial_report": User is asking about money spent, financial reports, expense sheets, category expenditure, worker spend, or daily/weekly/monthly spending.
        - "project_history": User is asking to search, filter, or view past completed construction projects.
        - "company_policy": User is asking about company rules, HR policies, site safety guidelines, or reimbursement limits.
        - "general_conversation": Greetings, thanks, general questions about Buildora capabilities.

        Return ONLY a valid JSON object: {{"intent": "label", "confidence": 0.95}}
        """
        raw = generate_gemini_response(contents=sys_p)
        if raw.startswith("```json"): raw = raw[7:]
        if raw.startswith("```"): raw = raw[3:]
        if raw.endswith("```"): raw = raw[:-3]
        data = json.loads(raw.strip())
        intent_val = data.get("intent", "general_conversation").lower()
        valid_intents = ["steel_estimation", "financial_report", "project_history", "company_policy", "general_conversation"]
        return intent_val if intent_val in valid_intents else "general_conversation"
    except Exception as e:
        logger.warning(f"Gemini intent classification fallback: {e}")
        m = message.lower()
        if any(k in m for k in ["steel", "takeoff", "rebar"]): return "steel_estimation"
        if any(k in m for k in ["past project", "historical", "previous project", "past projects"]): return "project_history"
        if any(k in m for k in ["expense", "spend", "spent", "spending", "financial", "budget", "cost"]): return "financial_report"
        if any(k in m for k in ["policy", "rule", "safety", "protocol", "guideline"]): return "company_policy"
        if any(k in m for k in ["sqft", "sq.ft", "square feet", "footing", "moment frame"]): return "steel_estimation"
        return "general_conversation"


SLOT_FALLBACK_QUESTIONS = {
    "total_covered_area_sqft": "What is the total covered area of the building in square feet (sqft)?",
    "covered_area_sqft": "What is the total covered area of the building in square feet (sqft)?",
    "area": "What is the total covered area of the building in square feet (sqft)?",
    "building_type": "What is the building type? (e.g. Commercial Office, Residential Apartment, Industrial Warehouse, Healthcare Facility, Retail Plaza)",
    "basement_count": "How many basement levels does the building have? (e.g. 0 for no basement, 1, 2)",
    "basement": "How many basement levels does the building have? (e.g. 0 for no basement, 1, 2)",
    "above_ground_floors": "How many above-ground floors does the building have? (e.g. 1 for Ground floor only, 4 for Ground + 3 upper floors)",
    "floors": "How many above-ground floors does the building have? (e.g. 1 for Ground floor only, 4 for Ground + 3 upper floors)",
    "structural_system": "What is the structural framing system?\n1. Reinforced Concrete Moment Frame\n2. Steel Moment Frame\n3. Wood / Light-Frame",
    "structural": "What is the structural framing system?\n1. Reinforced Concrete Moment Frame\n2. Steel Moment Frame\n3. Wood / Light-Frame",
    "foundation_type": "What is the foundation type?\n1. Spread Footing\n2. Mat Foundation\n3. Slab-on-Grade",
    "foundation": "What is the foundation type?\n1. Spread Footing\n2. Mat Foundation\n3. Slab-on-Grade",
    "floor_system": "What is the floor framing system?\n1. Beam & Slab\n2. Composite Metal Deck\n3. Wood Joist & Beam",
    "floor": "What is the floor framing system?\n1. Beam & Slab\n2. Composite Metal Deck\n3. Wood Joist & Beam",
    "location": "What is the project location? (e.g. Austin, Texas or Los Angeles, California)"
}


def deterministic_agent_fallback(agent_name: str, status: str, context_data: Dict[str, Any]) -> str:
    """Deterministic fallback explanation when Gemini is unavailable or quota is exhausted."""
    if status == "needs_input":
        next_field = context_data.get("next_prompt_field")
        if next_field and next_field in SLOT_FALLBACK_QUESTIONS:
            return SLOT_FALLBACK_QUESTIONS[next_field]
        missing = context_data.get("missing_fields", [])
        if missing and missing[0] in SLOT_FALLBACK_QUESTIONS:
            return SLOT_FALLBACK_QUESTIONS[missing[0]]
        return f"Please provide information for: {next_field or 'the next project parameter'}."

    if context_data.get("type") == "steel_takeoff_result" or "total_estimate" in context_data:
        p_data = context_data.get("payload", context_data)
        tot_est = p_data.get("total_estimate", {})
        conf = p_data.get("confidence", {})
        mkt = p_data.get("market_price", {})
        cost = p_data.get("material_cost", {})

        net_lbs = tot_est.get("estimated_net_lbs")
        net_tons = tot_est.get("estimated_net_us_tons")
        wastage_tons = tot_est.get("estimated_with_wastage_us_tons")

        lines = ["🏗️ **Buildora Steel Takeoff Final Historical Estimate**:\n"]
        if net_lbs and net_tons:
            lines.append(f"• **Estimated Net Rebar Weight**: {net_lbs:,.2f} lbs ({net_tons:,.2f} US short tons)")
        if wastage_tons:
            lines.append(f"• **Estimated With-Wastage Weight**: {tot_est.get('estimated_with_wastage_lbs', 0):,.2f} lbs ({wastage_tons:,.2f} US short tons)")
        if conf and conf.get("label"):
            lines.append(f"• **Historical Evidence Confidence**: {conf.get('label')} ({conf.get('display_score', 0)}/100)")
        if mkt and mkt.get("normalized_price_usd_per_us_ton"):
            lines.append(f"• **Verified Grade 60 Market Rate**: ${mkt.get('normalized_price_usd_per_us_ton'):,.2f} USD / US Short Ton ({mkt.get('location', 'US')})")
        if cost and cost.get("final_material_cost_usd"):
            lines.append(f"• **Total Estimated Steel Material Cost**: ${cost.get('final_material_cost_usd'):,.2f} USD ({cost.get('cost_basis', 'net_quantity')})")

        lines.append("\n*Note: This historical estimate is for planning/budgeting and is not a substitute for project-specific structural engineering calculations.*")
        return "\n".join(lines)

    return f"Result from {agent_name} (Status: {status}):\n{json.dumps(context_data, indent=2, default=str)}"


def format_agent_explanation_with_gemini(
    user_message: str,
    agent_name: str,
    status: str,
    context_data: Dict[str, Any],
) -> str:
    """
    Receives trusted structured AgentResult context and user question.
    Gemini generates a clean, conversational explanation without executing tools or altering numeric values.
    Falls back deterministically if Gemini is unavailable or quota is exhausted.
    """
    if context_data.get("type") == "company_policy_payload" or agent_name == "PolicyAgent":
        sources = context_data.get("sources", [])
        if status == "not_found" or not sources:
            return "No relevant company policy documents were found in the knowledge base matching your query."

        if not settings.GEMINI_API_KEY:
            lines = ["📜 **Buildora Company Policy Information**:\n"]
            for s in sources:
                page_str = f", Page {s['page_number']}" if s.get("page_number") else ""
                lines.append(f"• **{s['title']}** ({s['original_filename']}{page_str}):\n  {s['text']}\n")
            return "\n".join(lines)

        try:
            sys_p = f"""
You are the Buildora Enterprise Construction AI Assistant.
The PolicyAgent retrieved the following relevant policy document chunks from the company vector knowledge base.

User Question: "{user_message}"
Agent Status: {status}
Retrieved Sources Payload:
{json.dumps(sources, indent=2, default=str)}

Instructions:
1. Ground your answer strictly in the provided policy sources payload. Do NOT invent, assume, or fabricate any company policies or rules not explicitly supported by the text.
2. If the retrieved sources do not contain sufficient information to answer the question, state clearly that the indexed company policy documents do not contain relevant information for this question.
3. Citation formatting:
   - Identify the policy document by title or original filename (e.g. 'According to Employee Handbook 2026...').
   - Include the page number if page_number is available (e.g. 'page 7').
   - Do NOT invent or guess page numbers for DOCX or TXT files where page_number is null.
   - Do NOT expose internal technical fields like chunk_index, retrieval_score, Qdrant point IDs, or vector arrays in the user response.
4. Preserve exact numbers, dates, timelines, and procedures from the retrieved text.
5. Conflicting Policies: If the retrieved sources contain conflicting or differing guidance from multiple documents or versions, present both perspectives clearly and specify which document and page each rule comes from. Do NOT silently choose one over another.
6. Use clean Markdown formatting.
"""
            return generate_gemini_response(contents=sys_p)
        except Exception as e:
            logger.error(f"Gemini policy response formatting error: {e}")
            lines = ["📜 **Buildora Company Policy Information**:\n"]
            for s in sources:
                page_str = f", Page {s['page_number']}" if s.get("page_number") else ""
                lines.append(f"• **{s['title']}** ({s['original_filename']}{page_str}):\n  {s['text']}\n")
            return "\n".join(lines)

    if not settings.GEMINI_API_KEY:
        return deterministic_agent_fallback(agent_name, status, context_data)

    try:
        sys_p = f"""
You are the Buildora Enterprise Construction AI Assistant.
The backend Buildora Orchestrator and specialized agent '{agent_name}' executed and returned trusted structured results.

User Question: "{user_message}"
Agent Status: {status}
Trusted Agent Payload / Context:
{json.dumps(context_data, indent=2, default=str)}

Instructions:
1. Provide a professional, natural, and helpful explanation of the trusted agent payload.
2. CRITICAL: Do NOT alter or recalculate any numeric values (tons, sqft, rates, costs, spending totals).
3. CRITICAL: Do NOT claim you executed database tools or Python functions yourself.
4. If status is 'needs_input', ask the user naturally for the next missing information field needed for the takeoff.
5. If status is 'not_found', inform the user politely that no matching records were found.
6. Keep formatting clean using GitHub Markdown headers and bullet points.
"""
        return generate_gemini_response(contents=sys_p)
    except Exception as e:
        logger.error(f"Gemini response formatting error (falling back deterministically): {e}")
        return deterministic_agent_fallback(agent_name, status, context_data)

# -----------------------------------------------------------------------
# TYPE IMPORT — guard for SQLAlchemy Session
# -----------------------------------------------------------------------
try:
    from sqlalchemy.orm import Session as _Session
except ImportError:
    _Session = Any


def parse_receipt_with_gemini(image_path: str) -> Dict[str, Any]:
    """Parses receipt image using Gemini Vision AI. Raises an exception on configuration or API failure."""
    if not settings.GEMINI_API_KEY:
        logger.error("Gemini OCR request failed: GEMINI_API_KEY is not configured.")
        raise ValueError("GEMINI_API_KEY is missing or empty.")

    if not os.path.exists(image_path):
        logger.error(f"Receipt image file not found at path: {image_path}")
        raise FileNotFoundError(f"Receipt image file does not exist: {image_path}")

    try:
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
        Do not include markdown code block formatting (```json) in your final output.
        """
        raw_text = generate_gemini_response(contents=[prompt, image])
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        return json.loads(raw_text.strip())
    except Exception as e:
        logger.error(f"Gemini receipt OCR failed: {e}", exc_info=True)
        raise RuntimeError(f"Gemini Vision OCR service failed: {e}") from e


# -----------------------------------------------------------------------
# STEEL OPTION NORMALIZERS — strict keyword-only matching, NO digit fallback
# -----------------------------------------------------------------------

BUILDING_TYPE_OPTIONS = {
    "Residential Apartment": ["residential apartment", "residential multi-family", "apartment", "apartments", "residential building", "residential", "housing", "multi-family", "condo", "condominium", "residential project"],
    "Commercial Office": ["commercial office", "office building", "office tower", "commercial building", "commercial", "office", "commercial tower"],
    "Healthcare Facility": ["healthcare facility", "healthcare", "hospital", "medical center", "clinic"],
    "Industrial Warehouse": ["industrial warehouse", "warehouse", "industrial facility", "industrial building", "industrial", "factory"],
    "Retail Plaza": ["retail plaza", "retail store", "shopping center", "mall", "retail"],
    "Hospitality": ["hospitality", "hotel", "resort", "motel"],
    "Government Facility": ["government facility", "government building", "civic center", "municipal building"],
    "Commercial Event Hall": ["commercial event hall", "event hall", "convention center"]
}

STRUCTURAL_OPTIONS = {
    "Reinforced Concrete Moment Frame": [
        "reinforced concrete", "concrete moment", "rcc", "rc frame", "rc ",
        "concrete frame", "moment frame concrete", "reinforced"
    ],
    "Steel Moment Frame": [
        "steel moment", "steel frame", "structural steel", "smf", "steel structure"
    ],
    "Wood / Light-Frame": [
        "wood", "light-frame", "light frame", "timber", "wood frame"
    ],
}

FOUNDATION_OPTIONS = {
    "Spread Footing": ["spread footing", "spread footing", "individual footing", "isolated footing"],
    "Mat Foundation": ["mat foundation", "mat", "raft foundation", "raft"],
    "Slab-on-Grade": ["slab-on-grade", "slab on grade", "slab on ground", "grade slab"],
}

FLOOR_OPTIONS = {
    "Beam & Slab": ["beam & slab", "beam and slab", "beam slab", "beam-slab", "concrete slab and beam"],
    "Composite Metal Deck": ["composite metal deck", "metal deck", "composite deck", "steel deck"],
    "Wood Joist & Beam": ["wood joist", "wood joist & beam", "timber joist", "joist and beam"],
}

# Known US city/state locations for extraction
KNOWN_LOCATIONS = [
    "los angeles", "california", "san francisco", "san diego", "houston", "dallas",
    "austin", "san antonio", "fort worth", "texas", "new york", "new york city", "nyc",
    "chicago", "illinois", "miami", "florida", "seattle", "washington", "phoenix",
    "arizona", "denver", "colorado", "las vegas", "nevada", "atlanta", "georgia",
    "boston", "massachusetts", "portland", "oregon", "nashville", "tennessee",
    "charlotte", "north carolina", "indianapolis", "indiana", "columbus", "ohio",
    "memphis", "louisville", "kentucky", "oklahoma city", "oklahoma", "el paso",
    "albuquerque", "new mexico", "kansas city", "missouri", "virginia beach",
    "virginia", "raleigh", "milwaukee", "wisconsin"
]


def normalize_strict(text: str, options_map: Dict[str, List[str]]) -> Optional[str]:
    """Strictly matches user text to an official option using keyword lists only.
    Multi-word keywords: substring match. Single-word keywords: whole-word match.
    No digit fallback.
    """
    t = text.lower().strip()
    for canonical, keywords in options_map.items():
        for kw in keywords:
            if ' ' in kw:
                if kw in t:
                    return canonical
            else:
                if re.search(rf'\b{re.escape(kw)}\b', t):
                    return canonical
    return None


def extract_area_from_text(text: str) -> Optional[float]:
    """
    Extracts covered area from text. Supports:
    - "5000 sq.ft" / "5000 sqft" / "5000 square feet"
    - "35k" / "35K" (= 35000)
    - bare numbers like "3500" only when specific units not needed (contextual)
    """
    t = text.lower().strip()

    # 1. Explicit sqft patterns
    m = re.search(r'([\d,]+(?:\.\d+)?)\s*(?:sq\.?\s*ft|sqft|square\s*feet)', t)
    if m:
        try:
            return float(m.group(1).replace(',', ''))
        except Exception:
            pass

    # 2. "35k" / "35K" shorthand
    m = re.search(r'^(\d+(?:\.\d+)?)\s*k$', t)
    if m:
        try:
            return float(m.group(1)) * 1000
        except Exception:
            pass

    # 3. Bare positive integer/float (e.g., "3500") — accept ONLY when whole message is just a number
    m = re.match(r'^([\d,]+(?:\.\d+)?)\s*$', t)
    if m:
        try:
            val = float(m.group(1).replace(',', ''))
            if 100 <= val <= 5_000_000:
                return val
        except Exception:
            pass

    return None


def extract_basement_count_from_text(prompt: str, awaiting_slot: Optional[str]) -> Optional[int]:
    """
    Extracts basement level count from text.
    Supports:
    - "no basement" / "0 basements" / "without basement" -> 0
    - "one basement" / "1 basement" -> 1
    - "two basements" / "2 basements" -> 2
    - "three basements" / "3 basements" -> 3
    - corrections: "actually 2 basements", "make it two basements"
    """
    t = prompt.lower().strip()

    # Zero basements
    if any(k in t for k in ["no basement", "without basement", "zero basement", "0 basement", "no basements", "without basements", "0 basements"]):
        return 0

    word_to_num = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}

    # "N basement(s)" / "N basement level(s)"
    m = re.search(r'(\d+)\s*(?:basement\s*levels?|basement\s*floors?|basements?|basement)', t)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass

    for word, num in word_to_num.items():
        if re.search(rf'\b{word}\b\s*(?:basement\s*levels?|basement\s*floors?|basements?|basement)', t):
            return num

    if awaiting_slot in ("basement_count", "basement"):
        if t in ("no", "none", "zero", "0"):
            return 0
        m = re.match(r'^(\d+)\s*$', t)
        if m:
            v = int(m.group(1))
            if 0 <= v <= 20:
                return v

    return None


def extract_above_ground_floors_from_text(prompt: str, awaiting_slot: Optional[str]) -> Optional[int]:
    """
    Extracts above-ground floor count.
    Convention: Ground Floor + upper occupied floors.
    Examples:
    - "Ground plus 3" / "Ground + 3 upper floors" -> 1 (Ground) + 3 = 4 above_ground_floors
    - "Ground plus 4" -> 1 + 4 = 5
    - "Ground plus three" -> 1 + 3 = 4
    - "4 floors" / "4 stories" -> 4
    - "1 story" / "ground floor" -> 1
    Basements are NOT included in above_ground_floors.
    """
    t = prompt.lower().strip()
    word_to_num = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                   "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

    # 1. "Ground + N" / "Ground plus N" / "Ground and N"
    m_ground = re.search(r'ground\s*(?:\+|\s*plus\s*|\s*and\s*)\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten)', t)
    if m_ground:
        val_str = m_ground.group(1)
        upper_count = int(val_str) if val_str.isdigit() else word_to_num.get(val_str, 0)
        return 1 + upper_count

    # 2. "N floors/stories"
    m_floors = re.search(r'(\d+)\s*(?:above\s*ground\s*)?(?:floor|floors|story|stories|storey|storeys)', t)
    if m_floors:
        try:
            return int(m_floors.group(1))
        except Exception:
            pass

    for word, num in word_to_num.items():
        if re.search(rf'\b{word}\b\s*(?:above\s*ground\s*)?(?:floor|floors|story|stories)', t):
            return num

    if awaiting_slot in ("above_ground_floors", "floors"):
        m = re.match(r'^(\d+)\s*$', t)
        if m:
            v = int(m.group(1))
            if 1 <= v <= 200:
                return v

    return None


def extract_floors_from_text(text: str) -> Optional[int]:
    """Alias helper for extract_above_ground_floors_from_text."""
    return extract_above_ground_floors_from_text(text, None)


def extract_location_from_text(text: str) -> Optional[str]:
    """Extracts project location from user text."""
    t = text.lower().strip()
    for loc in sorted(KNOWN_LOCATIONS, key=len, reverse=True):
        if loc in t:
            return loc.title()
    if re.match(r'^[a-zA-Z ,\.]+$', text.strip()) and len(text.strip()) >= 3:
        return text.strip().title()
    return None


def extract_steel_slots_from_prompt(
    prompt: str,
    awaiting_slot: Optional[str],
    current_ctx: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Context-aware slot extractor for steel estimation supporting 8 required inputs.
    Enforces steel_grade = "Grade 60" as a fixed system rule.
    """
    extracted: Dict[str, Any] = {}
    prompt_lower = prompt.lower().strip()

    # Enforce fixed system property
    extracted["steel_grade"] = "Grade 60"

    # ---- 1. TOTAL COVERED AREA ----
    area_val = extract_area_from_text(prompt)
    if area_val is not None:
        extracted["total_covered_area_sqft"] = area_val
        extracted["covered_area_sqft"] = area_val
    elif awaiting_slot in ("total_covered_area_sqft", "area"):
        m = re.match(r'^([\d,]+(?:\.\d+)?)\s*k?$', prompt_lower)
        if m:
            raw = m.group(0).replace(',', '')
            try:
                val = float(raw[:-1]) * 1000 if raw.endswith('k') else float(raw)
                if 100 <= val <= 5_000_000:
                    extracted["total_covered_area_sqft"] = val
                    extracted["covered_area_sqft"] = val
            except Exception:
                pass

    # ---- 2. BUILDING TYPE ----
    btype = normalize_strict(prompt, BUILDING_TYPE_OPTIONS)
    if btype:
        extracted["building_type"] = btype
    elif awaiting_slot == "building_type":
        if len(prompt_lower) >= 3 and not prompt_lower.isdigit():
            extracted["building_type"] = prompt.strip().title()

    # ---- 3. BASEMENT COUNT ----
    b_count = extract_basement_count_from_text(prompt, awaiting_slot)
    if b_count is not None:
        extracted["basement_count"] = b_count

    # ---- 4. ABOVE-GROUND FLOORS ----
    ag_floors = extract_above_ground_floors_from_text(prompt, awaiting_slot)
    if ag_floors is not None:
        extracted["above_ground_floors"] = ag_floors
        extracted["floors"] = ag_floors

    # ---- 5. STRUCTURAL SYSTEM ----
    if awaiting_slot in (None, "structural_system", "structural"):
        struct = normalize_strict(prompt, STRUCTURAL_OPTIONS)
        if struct:
            extracted["structural_system"] = struct
        elif awaiting_slot in ("structural_system", "structural"):
            m = re.match(r'^([123])\s*$', prompt_lower)
            if m:
                idx_map = {"1": "Reinforced Concrete Moment Frame", "2": "Steel Moment Frame", "3": "Wood / Light-Frame"}
                extracted["structural_system"] = idx_map[m.group(1)]
    else:
        struct = normalize_strict(prompt, STRUCTURAL_OPTIONS)
        if struct:
            extracted["structural_system"] = struct

    # ---- 6. FOUNDATION TYPE ----
    if awaiting_slot in (None, "foundation_type", "foundation"):
        found = normalize_strict(prompt, FOUNDATION_OPTIONS)
        if found:
            extracted["foundation_type"] = found
        elif awaiting_slot in ("foundation_type", "foundation"):
            m = re.match(r'^([123])\s*$', prompt_lower)
            if m:
                idx_map = {"1": "Spread Footing", "2": "Mat Foundation", "3": "Slab-on-Grade"}
                extracted["foundation_type"] = idx_map[m.group(1)]
    else:
        found = normalize_strict(prompt, FOUNDATION_OPTIONS)
        if found:
            extracted["foundation_type"] = found

    # ---- 7. FLOOR SYSTEM ----
    if awaiting_slot in (None, "floor_system", "floor"):
        floor_sys = normalize_strict(prompt, FLOOR_OPTIONS)
        if floor_sys:
            extracted["floor_system"] = floor_sys
        elif awaiting_slot in ("floor_system", "floor"):
            m = re.match(r'^([123])\s*$', prompt_lower)
            if m:
                idx_map = {"1": "Beam & Slab", "2": "Composite Metal Deck", "3": "Wood Joist & Beam"}
                extracted["floor_system"] = idx_map[m.group(1)]
    else:
        floor_sys = normalize_strict(prompt, FLOOR_OPTIONS)
        if floor_sys:
            extracted["floor_system"] = floor_sys

    # ---- 8. LOCATION ----
    if awaiting_slot == "location":
        loc_val = extract_location_from_text(prompt)
        if loc_val:
            extracted["location"] = loc_val
    elif any(loc in prompt_lower for loc in KNOWN_LOCATIONS):
        loc_val = extract_location_from_text(prompt)
        if loc_val:
            extracted["location"] = loc_val

    return extracted


def extract_project_filters(prompt: str) -> Dict[str, Any]:
    """
    Extracts structured project database filter criteria from natural language text.
    Handles phrases like:
    - "area more than 45000 sqft", "area over 45k", "> 45000", "sqft < 50000"
    - "structural design is RCC", "steel frame", "reinforced concrete", "wood"
    - "floors = 6", "6 floors", "6 stories"
    - "foundation is mat foundation", "spread footing", "slab on grade"
    - "steel tonnage over 100", "over 100 tons of steel", "> 100 tons steel"
    - "budget under 100k", "cost over $150,000"
    - "Texas", "California", "Houston"
    """
    t = prompt.lower().strip()
    extracted: Dict[str, Any] = {}

    # 1. Minimum / Maximum Sqft
    min_sqft_match = re.search(r'(?:area|sqft|sq\s*ft|covered area)\s*(?:more than|over|above|greater than|>=?|>)\s*([\d,]+(?:\.\d+)?)\s*k?', t)
    if not min_sqft_match:
        min_sqft_match = re.search(r'(?:more than|over|above|greater than|>=?|>)\s*([\d,]+(?:\.\d+)?)\s*k?\s*(?:sqft|sq\s*ft|square feet)', t)
    if min_sqft_match:
        val_str = min_sqft_match.group(1).replace(',', '')
        try:
            val = float(val_str)
            if 'k' in min_sqft_match.group(0): val *= 1000
            extracted["min_sqft"] = val
        except Exception:
            pass

    max_sqft_match = re.search(r'(?:area|sqft|sq\s*ft|covered area)\s*(?:less than|under|below|<=?|<)\s*([\d,]+(?:\.\d+)?)\s*k?', t)
    if not max_sqft_match:
        max_sqft_match = re.search(r'(?:less than|under|below|<=?|<)\s*([\d,]+(?:\.\d+)?)\s*k?\s*(?:sqft|sq\s*ft|square feet)', t)
    if max_sqft_match:
        val_str = max_sqft_match.group(1).replace(',', '')
        try:
            val = float(val_str)
            if 'k' in max_sqft_match.group(0): val *= 1000
            extracted["max_sqft"] = val
        except Exception:
            pass

    # Bare sqft specification like "around 45000 sqft" or "45000 sqft"
    if "min_sqft" not in extracted and "max_sqft" not in extracted:
        sqft_val = extract_area_from_text(prompt)
        if sqft_val and ("sqft" in t or "sq ft" in t or "square feet" in t or "area" in t):
            extracted["min_sqft"] = sqft_val * 0.85
            extracted["max_sqft"] = sqft_val * 1.15

    # 2. Structural System
    struct = normalize_strict(prompt, STRUCTURAL_OPTIONS)
    if struct:
        extracted["structural_system"] = struct

    # 3. Floors (Requires explicit word 'floor', 'floors', 'story', 'stories')
    floors_match = re.search(r'\b(\d+)\s*(?:floors?|stories|story)\b', t)
    if not floors_match:
        floors_match = re.search(r'\bfloors?\s*(?:=|\bis|\bof)?\s*(\d+)\b', t)
    if floors_match:
        try:
            extracted["floors"] = int(floors_match.group(1))
        except Exception:
            pass

    # 4. Foundation Type
    found = normalize_strict(prompt, FOUNDATION_OPTIONS)
    if found:
        extracted["foundation_type"] = found

    # 5. Steel Tonnage (Requires explicit word 'steel', 'tonnage', 'tons', 'rebar')
    steel_min_match = re.search(r'(?:steel|tonnage|tons|rebar)\s*(?:over|more than|above|greater than|>=?|>)\s*([\d,]+(?:\.\d+)?)', t)
    if not steel_min_match:
        steel_min_match = re.search(r'(?:over|more than|above|greater than|>=?|>)\s*([\d,]+(?:\.\d+)?)\s*(?:tons|ton|t)\s*(?:of\s*steel|steel)?', t)
    if steel_min_match and ("steel" in t or "ton" in t or "rebar" in t):
        try:
            extracted["min_steel_tons"] = float(steel_min_match.group(1).replace(',', ''))
        except Exception:
            pass

    steel_max_match = re.search(r'(?:steel|tonnage|tons|rebar)\s*(?:under|less than|below|<=?|<)\s*([\d,]+(?:\.\d+)?)', t)
    if not steel_max_match:
        steel_max_match = re.search(r'(?:under|less than|below|<=?|<)\s*([\d,]+(?:\.\d+)?)\s*(?:tons|ton|t)\s*(?:of\s*steel|steel)?', t)
    if steel_max_match and ("steel" in t or "ton" in t or "rebar" in t):
        try:
            extracted["max_steel_tons"] = float(steel_max_match.group(1).replace(',', ''))
        except Exception:
            pass

    # 6. Budget
    budget_min_match = re.search(r'(?:budget|cost|price)\s*(?:over|more than|above|greater than|>=?|>)\s*\$?([\d,]+(?:\.\d+)?)\s*k?', t)
    if budget_min_match:
        try:
            val = float(budget_min_match.group(1).replace(',', ''))
            if 'k' in budget_min_match.group(0): val *= 1000
            extracted["min_budget"] = val
        except Exception:
            pass

    budget_max_match = re.search(r'(?:budget|cost|price)\s*(?:under|less than|below|<=?|<)\s*\$?([\d,]+(?:\.\d+)?)\s*k?', t)
    if budget_max_match:
        try:
            val = float(budget_max_match.group(1).replace(',', ''))
            if 'k' in budget_max_match.group(0): val *= 1000
            extracted["max_budget"] = val
        except Exception:
            pass

    # 7. Location
    loc = extract_location_from_text(prompt)
    if loc and loc.lower() not in ["area", "floors", "steel", "budget"]:
        extracted["location"] = loc

    return extracted


def extract_expense_filters(prompt: str) -> Dict[str, Any]:
    """
    Extracts structured expense report filter criteria from natural language text.
    """
    t = prompt.lower().strip()
    extracted: Dict[str, Any] = {}

    s_date, e_date, date_label = parse_date_range_from_prompt(prompt)
    if any(k in t for k in ["today", "yesterday", "week", "month", "september", "august", "october", "daily", "weekly", "monthly"]):
        extracted["start_date"] = s_date
        extracted["end_date"] = e_date
        extracted["date_label"] = date_label

    workers = ["john worker", "sarah admin", "david hr", "john", "sarah", "david"]
    for w in workers:
        if re.search(rf'\b{re.escape(w)}\b', t):
            extracted["user_filter"] = w.title()
            break

    cats = ["materials", "equipment", "fuel", "tools", "misc", "supplies"]
    for c in cats:
        if re.search(rf'\b{re.escape(c)}\b', t):
            extracted["category_filter"] = c.title()
            break

    vendors = ["home depot", "austin high-rise", "dallas medical", "houston industrial"]
    for v in vendors:
        if v in t:
            extracted["project_filter"] = v.title()
            break

    amt_over = re.search(r'(?:amount|spend|spent|over|more than|>=?|>)\s*\$?([\d,]+(?:\.\d+)?)', t)
    if amt_over and ("over" in t or "more than" in t or ">" in t or "spent" in t):
        try:
            extracted["min_amount"] = float(amt_over.group(1).replace(',', ''))
        except Exception:
            pass

    amt_under = re.search(r'(?:under|less than|<=?|<)\s*\$?([\d,]+(?:\.\d+)?)', t)
    if amt_under and ("under" in t or "less than" in t or "<" in t):
        try:
            extracted["max_amount"] = float(amt_under.group(1).replace(',', ''))
        except Exception:
            pass

    return extracted


def extract_project_filters_with_gemini(prompt: str, existing_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Uses Gemini structured extraction to parse natural language filter criteria.
    Leaves fields null if not mentioned by the user.
    """
    extracted: Dict[str, Any] = {}
    if settings.GEMINI_API_KEY:
        try:
            sys_p = f"""
            You are a Database Filter Extractor AI for a construction project system.
            User prompt: "{prompt}"
            Existing active session filters: {json.dumps({k: str(v) for k, v in existing_context.items() if v is not None and k != 'active'})}

            Analyze the user's message and extract any requested project filter criteria.
            Return ONLY a valid JSON object with these exact keys:
            {{
                "min_sqft": float or null,
                "max_sqft": float or null,
                "structural_system": string or null,
                "floors": integer or null,
                "foundation_type": string or null,
                "min_steel_tons": float or null,
                "max_steel_tons": float or null,
                "min_budget": float or null,
                "max_budget": float or null,
                "location": string or null
            }}

            Instructions:
            - Set value ONLY if user explicitly specified or implied that filter in their text.
            - If user typed "area > 45000" or "more than 45000 sqft", set min_sqft = 45000.0.
            - If user typed "steel over 100 tons" or "more than 100 tons of steel", set min_steel_tons = 100.0.
            - Do not include markdown code block formatting in your output if possible.
            """
            raw = generate_gemini_response(contents=sys_p)
            if raw.startswith("```json"): raw = raw[7:]
            if raw.startswith("```"): raw = raw[3:]
            if raw.endswith("```"): raw = raw[:-3]
            parsed = json.loads(raw.strip())
            for k, v in parsed.items():
                if v is not None:
                    extracted[k] = v
        except Exception as e:
            logger.error(f"Gemini project filter extraction failed: {e}")

    # Combine with local rule-based extractor for reliable coverage
    local_ext = extract_project_filters(prompt)
    for k, v in local_ext.items():
        if k not in extracted or extracted[k] is None:
            extracted[k] = v

    return extracted


def extract_expense_filters_with_gemini(prompt: str, existing_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Uses Gemini structured extraction to parse natural language expense filter criteria.
    """
    extracted: Dict[str, Any] = {}
    if settings.GEMINI_API_KEY:
        try:
            sys_p = f"""
            You are an Expense Filter Extractor AI for a construction financial database.
            User prompt: "{prompt}"
            Existing active session filters: {json.dumps({k: str(v) for k, v in existing_context.items() if v is not None and k != 'active'})}

            Analyze the user's message and extract any requested expense filter criteria.
            Return ONLY a valid JSON object with these exact keys:
            {{
                "user_filter": string or null,
                "project_filter": string or null,
                "category_filter": string or null,
                "min_amount": float or null,
                "max_amount": float or null
            }}

            Instructions:
            - Set value ONLY if specified by the user.
            - Do not include markdown code block formatting in output.
            """
            raw = generate_gemini_response(contents=sys_p)
            if raw.startswith("```json"): raw = raw[7:]
            if raw.startswith("```"): raw = raw[3:]
            if raw.endswith("```"): raw = raw[:-3]
            parsed = json.loads(raw.strip())
            for k, v in parsed.items():
                if v is not None:
                    extracted[k] = v
        except Exception as e:
            logger.error(f"Gemini expense filter extraction failed: {e}")

    local_ext = extract_expense_filters(prompt)
    for k, v in local_ext.items():
        if k not in extracted or extracted[k] is None:
            extracted[k] = v

    return extracted


def _gemini_call(system_prompt: str) -> Optional[str]:
    """Helper: Call Gemini using the central helper and return text, or None on error."""
    if not settings.GEMINI_API_KEY:
        return None
    try:
        return generate_gemini_response(contents=system_prompt)
    except Exception as e:
        logger.error(f"Gemini API call failed in _gemini_call: {e}")
        return None


# -----------------------------------------------------------------------
# MAIN AGENT ENTRY POINT
# -----------------------------------------------------------------------

def process_unified_ai_assistant_query(
    prompt: str,
    db: Any,
    current_user: Any = None,
    user_role: str = "WORKER",
    session_id: Optional[str] = "default_session"
) -> Dict[str, Any]:
    """
    Intelligent Multi-Feature AI Agent Engine.
    Role-isolated: Admin (3 tools) vs Worker (3 tools).
    Steel Estimation: context-aware one-question-at-a-time conversational slot filling.
    """
    prompt_lower = prompt.lower().strip()
    sess_id = session_id or "default_session"
    session_data = session_manager.get_session(sess_id)

    # ------------------------------------------------------------------
    # 0. AUTHORITATIVE ROLE FROM JWT / DB CONTEXT / CLIENT ROLE
    # ------------------------------------------------------------------
    if user_role and user_role.upper() in ["ADMIN", "HR_MANAGER", "WORKER"]:
        role = user_role.upper()
    elif current_user and hasattr(current_user, 'role') and current_user.role:
        role = current_user.role.upper()
    else:
        role = "WORKER"

    # ------------------------------------------------------------------
    # WORKER DOMAIN — Leave, Policy, Balance only
    # ------------------------------------------------------------------
    if role == "WORKER":
        # Hard block: Admin-only tools
        admin_keywords = [
            "estimate steel", "steel takeoff", "calculate steel", "steel cost",
            "past project", "project database", "historical project",
            "financial report", "expense report", "expense sheet",
            "total project", "vendor financial", "procurement"
        ]
        if any(k in prompt_lower for k in admin_keywords):
            return {
                "answer": "🔒 **Access Restricted**: Financial project reports, past project database search, and Grade 60 Steel Estimation are restricted to the Admin Operations Console.\n\nAs a Field Worker, I can assist you with:\n1. 📝 **Leave Requests** (Requests < 3 days auto-approved)\n2. 📊 **Check Your Leave Balance**\n3. 📜 **Company Policies & Site Safety Guidelines**",
                "intent": "guardrail",
                "auto_approved_leave": False
            }

        # Leave Balance Check
        if any(k in prompt_lower for k in ["how many", "balance", "remaining", "left", "check leave", "my leaves", "days left", "leave days"]):
            leave_data = query_leave_balance_db(db, current_user)
            sys_prompt = (
                f'You are the Buildora Field Employee AI Assistant. User asked: "{prompt}"\n'
                f'Leave Database: {json.dumps(leave_data)}\n'
                'Instructions: Provide a clear, friendly leave balance summary. Mention that requests under 3 days are auto-approved. Do not expose internal tool names.'
            )
            answer = _gemini_call(sys_prompt)
            if not answer:
                d = leave_data
                answer = (
                    f"📊 **Your Leave Balance**:\n\n"
                    f"• Annual Entitlement: **{d['annual_entitlement_days']} days**\n"
                    f"• Used / Approved: **{d['used_approved_days']} days**\n"
                    f"• Remaining: **{d['remaining_days']} days**\n\n"
                    f"Requests under 3 days are automatically approved!"
                )
            return {"answer": answer, "intent": "leave_balance", "auto_approved_leave": False}

        # Leave Request & Auto-Approval
        if any(k in prompt_lower for k in ["request leave", "apply leave", "take leave", "day off", "sick leave", "vacation", "i want leave"]):
            days_match = re.search(r'(\d+)\s*(?:day|days)', prompt_lower)
            num_days = int(days_match.group(1)) if days_match else 2
            if num_days < 3:
                return {
                    "answer": f"✅ **Leave Request Auto-Approved!**\n\nYour request for **{num_days} day(s)** has been cleared automatically under Buildora HR Policy (requests < 3 days are auto-approved).",
                    "intent": "leave_request",
                    "auto_approved_leave": True
                }
            else:
                return {
                    "answer": f"⏳ **Leave Request Submitted for HR Review**\n\nYour request for **{num_days} day(s)** has been submitted. It exceeds the 3-day auto-approval limit and will be reviewed by HR management.",
                    "intent": "leave_request",
                    "auto_approved_leave": False
                }

        # Company Policy KB — RAG Retrieval
        sources = query_company_policy_kb(db, prompt)
        if not sources:
            return {
                "answer": "📜 **Buildora Company Policy Information**:\n\nNo relevant company policy documents matching your request were found in the knowledge base.",
                "intent": "policy",
                "auto_approved_leave": False
            }

        sys_prompt = f"""
You are the Buildora Field Employee AI Assistant. User asked: "{prompt}"

Retrieved Company Policy Chunks:
{json.dumps(sources, indent=2, default=str)}

Instructions:
1. Provide a clear, grounded summary answering the user's question using ONLY the provided policy chunks.
2. Do NOT invent or fabricate company policies not present in the sources.
3. Include document title / filename and page number where page_number is available. Do not invent page numbers for DOCX/TXT files (where page_number is null).
4. Do NOT expose internal fields like chunk_index, retrieval_score, Qdrant point IDs, or vectors.
5. If retrieved sources contain conflicting policies, state clearly that different documents specify conflicting rules and cite each document/page.
6. Preserve exact numbers, dates, monetary amounts, and procedures.
"""
        answer = _gemini_call(sys_prompt)
        if not answer:
            policy_lines = ["📜 **Buildora Company Policy Information**:\n"]
            for s in sources:
                page_str = f", Page {s['page_number']}" if s.get("page_number") else ""
                policy_lines.append(f"• **{s['title']}** ({s['original_filename']}{page_str}):\n  {s['text']}\n")
            answer = "\n".join(policy_lines)
        return {"answer": answer, "intent": "policy", "auto_approved_leave": False}

    # ------------------------------------------------------------------
    # ADMIN DOMAIN — ONLY: Historical Projects, Expense Reports, Steel Estimation
    # ------------------------------------------------------------------

    steel_ctx = session_data.get("steel_context", {})
    steel_is_active = steel_ctx.get("active", False)
    awaiting_slot = session_manager.get_awaiting_slot(sess_id)

    # Detect steel estimation intent (new trigger OR ongoing session)
    steel_trigger_keywords = [
        "estimate steel", "steel estimation", "steel takeoff", "steel cost",
        "cost of steel", "calculate steel", "steel rebar", "estimate the cost of steel"
    ]
    is_new_steel_request = any(k in prompt_lower for k in steel_trigger_keywords)

    # ------------------------------------------------------------------
    # 1. STEEL ESTIMATION — Context-Aware Conversational Slot Filling
    # ------------------------------------------------------------------
    if is_new_steel_request or steel_is_active:

        # If it's a new request, reset any stale session
        if is_new_steel_request and not steel_is_active:
            session_manager.clear_steel_context(sess_id)
            session_manager.mark_steel_active(sess_id)
            steel_ctx = session_manager.get_session(sess_id)["steel_context"]

        # Extract slots from current message using context-awareness
        extracted = extract_steel_slots_from_prompt(prompt, awaiting_slot, steel_ctx)
        steel_ctx = session_manager.update_steel_context(sess_id, extracted)

        area = steel_ctx.get("covered_area_sqft")
        floors = steel_ctx.get("floors")
        struct_sys = steel_ctx.get("structural_system")
        found_type = steel_ctx.get("foundation_type")
        floor_sys = steel_ctx.get("floor_system")
        loc = steel_ctx.get("location")

        # ---- ASK ONLY THE NEXT MISSING SLOT (one question at a time) ----

        if not area:
            session_manager.set_awaiting_slot(sess_id, "area")
            msg = "Sure! Let's estimate the steel cost step by step.\n\nFirst, what is the **covered area** of the project in square feet?\n*(For example: 5,000 sq.ft or just 5000)*"
            if is_new_steel_request and any(v is not None for v in [floors, struct_sys, found_type, floor_sys, loc]):
                # User sent info but no area detected — ask specifically
                msg = "I can see you've provided some project details. To start, could you confirm the **covered area** in square feet?\n*(For example: 5,000 sq.ft)*"
            return {"answer": msg, "intent": "steel_estimator", "auto_approved_leave": False}

        if not floors:
            session_manager.set_awaiting_slot(sess_id, "floors")
            return {
                "answer": f"Got it — **{area:,.0f} sq.ft**.\n\nHow many **floors** does the building have?\n*(Enter a number, e.g. 2)*",
                "intent": "steel_estimator",
                "auto_approved_leave": False
            }

        if not struct_sys:
            session_manager.set_awaiting_slot(sess_id, "structural")
            return {
                "answer": f"Got it — **{int(floors)} floor(s)**.\n\nWhich **structural system** are you using?\n\n1. Reinforced Concrete Moment Frame\n2. Steel Moment Frame\n3. Wood / Light-Frame\n\n*(Type the number or name)*",
                "intent": "steel_estimator",
                "auto_approved_leave": False
            }

        if not found_type:
            session_manager.set_awaiting_slot(sess_id, "foundation")
            return {
                "answer": f"Great — **{struct_sys}**.\n\nWhich **foundation type** are you using?\n\n1. Spread Footing\n2. Mat Foundation\n3. Slab-on-Grade\n\n*(Type the number or name)*",
                "intent": "steel_estimator",
                "auto_approved_leave": False
            }

        if not floor_sys:
            session_manager.set_awaiting_slot(sess_id, "floor")
            return {
                "answer": f"Understood — **{found_type}**.\n\nWhich **floor system** are you using?\n\n1. Beam & Slab\n2. Composite Metal Deck\n3. Wood Joist & Beam\n\n*(Type the number or name)*",
                "intent": "steel_estimator",
                "auto_approved_leave": False
            }

        if not loc:
            session_manager.set_awaiting_slot(sess_id, "location")
            return {
                "answer": f"Almost done — **{floor_sys}**.\n\nWhat is the **project location**?\n*(For example: California, Los Angeles CA, Texas, Houston TX)*",
                "intent": "steel_estimator",
                "auto_approved_leave": False
            }

        # ---- ALL 6 INPUTS COLLECTED — RUN ESTIMATION ----
        session_manager.set_awaiting_slot(sess_id, None)

        # Step 1: Historical Project DB — find similar projects
        proj_dict = query_historical_projects_db(db, sqft_filter=area, location_filter=loc)
        similar_projects = proj_dict.get("projects", []) if isinstance(proj_dict, dict) else (proj_dict or [])

        # Step 2: Engineering quantity estimate from historical data or baseline
        if similar_projects:
            # Use average steel density from similar historical projects
            avg_steel_per_sqft = sum(p["steel_tons_used"] / max(p["sqft"], 1) for p in similar_projects) / len(similar_projects)
            total_sqft = area * floors
            total_weight_tons = round(total_sqft * avg_steel_per_sqft, 2)
            quantity_basis = f"derived from {len(similar_projects)} similar historical project(s)"
        else:
            # Engineering baseline by structural system
            density_lbs_per_sqft = {
                "Reinforced Concrete Moment Frame": 0.85,
                "Steel Moment Frame": 1.10,
                "Wood / Light-Frame": 0.40,
            }.get(struct_sys, 0.85)
            total_sqft = area * floors
            total_weight_tons = round((total_sqft * density_lbs_per_sqft) / 2000.0, 2)
            quantity_basis = f"engineering baseline ({density_lbs_per_sqft} lbs/sqft for {struct_sys})"

        # Step 3: Tavily live market price for user's location
        tavily_data = get_market_steel_price(location=loc)
        price_per_ton = tavily_data.get("market_price_per_ton")
        price_found = tavily_data.get("price_found", False)
        query_used = tavily_data.get("query_used", "")
        web_sources = tavily_data.get("web_sources", [])
        retrieval_date = tavily_data.get("retrieval_date", datetime.date.today().strftime("%B %d, %Y"))

        structured_payload = {
            "project_inputs": {
                "covered_area_sqft": area,
                "floors": floors,
                "total_structural_sqft": total_sqft,
                "structural_system": struct_sys,
                "foundation_type": found_type,
                "floor_system": floor_sys,
                "location": loc
            },
            "historical_evidence": {
                "similar_projects_found": len(similar_projects),
                "similar_projects": similar_projects[:3],
                "quantity_basis": quantity_basis,
                "estimated_steel_tons": total_weight_tons
            },
            "market_price_info": {
                "location": loc,
                "search_query": query_used,
                "retrieval_date": retrieval_date,
                "price_found": price_found,
                "market_price_per_ton_usd": price_per_ton,
                "sources": web_sources
            },
            "estimated_material_cost_usd": round(total_weight_tons * price_per_ton, 2) if price_per_ton else None
        }

        # Clear session state
        session_manager.clear_steel_context(sess_id)

        # Step 4: Gemini synthesizes the final response
        sys_prompt = f"""
You are the Buildora Enterprise Construction Estimator AI. The user completed a steel takeoff estimation conversation.

Structured Estimation Payload:
{json.dumps(structured_payload, indent=2)}

Instructions:
1. Begin with: "Perfect — I have all the project details. Here is your steel cost estimate:"
2. Show a clean section: **Project Details** listing all 6 inputs.
3. Show **Historical Comparison**: state how many similar projects were found and what basis was used for the quantity estimate.
4. Show **Current Market Information**: Location, Grade 60 rebar price ($/ton), Source (with markdown link if URL available), Retrieval date.
   - If price_found is false, clearly state that no reliable local price was found and do NOT fabricate a price.
5. Show **Estimated Steel Quantity**: X tons (with basis explanation).
6. Show **Estimated Material Cost**: Quantity × Price = Total.
   - If price was not found reliably, say cost cannot be calculated and suggest user provide a local quote.
7. Do NOT expose internal tool names, session variables, or raw JSON.
8. Do NOT invent numbers — use ONLY the values in the payload.
"""
        answer = _gemini_call(sys_prompt)
        if not answer:
            # Fallback formatter
            src_lines = []
            for s in web_sources[:2]:
                src_lines.append(f"  • [{s['title']}]({s['url']}) — *\"{s.get('snippet','')[:100]}\"* (Retrieved: {retrieval_date})")
            src_block = "\n".join(src_lines) if src_lines else f"  • Benchmark rate for {loc}"

            cost_line = (
                f"**${structured_payload['estimated_material_cost_usd']:,.2f} USD**"
                if structured_payload["estimated_material_cost_usd"]
                else "Unable to calculate — reliable local market price not found. Please provide a local quoted price."
            )

            price_line = (
                f"**${price_per_ton:,.2f} USD / US Ton**"
                if price_found and price_per_ton
                else "No reliable local price found via market search"
            )

            answer = (
                f"**Steel Takeoff Estimation**\n\n"
                f"**Project Details**\n"
                f"• Covered Area: {area:,.0f} sq.ft\n"
                f"• Floors: {int(floors)}\n"
                f"• Structural System: {struct_sys}\n"
                f"• Foundation: {found_type}\n"
                f"• Floor System: {floor_sys}\n"
                f"• Location: {loc}\n\n"
                f"**Historical Comparison**\n"
                f"• Similar projects found: {len(similar_projects)}\n"
                f"• Quantity basis: {quantity_basis}\n"
                f"• Estimated steel quantity: **{total_weight_tons:,.2f} US Tons**\n\n"
                f"**Current Market Information ({loc})**\n"
                f"• Grade: Grade 60 Rebar\n"
                f"• Market price: {price_line}\n"
                f"• Market search query: `{query_used}`\n"
                f"• Sources:\n{src_block}\n\n"
                f"**Estimated Steel Material Cost**\n"
                f"{cost_line}"
            )

        return {"answer": answer, "intent": "steel_estimator", "auto_approved_leave": False}

    # ------------------------------------------------------------------
    # 2. FINANCIAL EXPENSE REPORT AGENT (Admin Only)
    # ------------------------------------------------------------------
    expense_keywords = [
        "expense report", "expense sheet", "financial report", "show expenses",
        "daily expense", "weekly expense", "monthly expense", "today", "yesterday",
        "spent today", "spent this week", "spending", "receipt breakdown",
        "show me the", "how much was spent", "how much did", "this week", "last week",
        "this month", "last month", "september", "august", "october"
    ]
    if any(k in prompt_lower for k in expense_keywords) or session_data.get("last_intent") == "financial_expense":
        session_data["last_intent"] = "financial_expense"

        # Extract expense filter criteria from prompt using Gemini & update session context
        curr_exp_ctx = session_manager.get_expense_filter_context(sess_id)
        extracted_exp = extract_expense_filters_with_gemini(prompt, curr_exp_ctx)
        active_exp_ctx = session_manager.update_expense_filter_context(sess_id, extracted_exp)

        # Query database with dynamic parameterized filters
        financial_payload = query_financial_expenses_db(
            db,
            prompt=prompt,
            start_date=active_exp_ctx.get("start_date"),
            end_date=active_exp_ctx.get("end_date"),
            project_filter=active_exp_ctx.get("project_filter"),
            user_filter=active_exp_ctx.get("user_filter"),
            category_filter=active_exp_ctx.get("category_filter"),
            min_amount=active_exp_ctx.get("min_amount"),
            max_amount=active_exp_ctx.get("max_amount")
        )

        sys_prompt = f"""
You are the Buildora Enterprise Financial Controller AI. User asked: "{prompt}"

Live Parameterized Database Financial Payload:
{json.dumps(financial_payload, indent=2)}

Instructions:
1. Provide a professional financial report dynamically tailored to the user's exact query and filters.
2. The FIRST line must be the report header and date period, e.g.:
   "**Financial Expense Report — {financial_payload['date_period']}**"
3. If filters were applied (worker, project, category, amount range), list them clearly in a **Applied Filters** bullet section.
4. Include Total Spend ($USD) and Total Verified Receipts count matching the filter.
5. Include Project Breakdown (spend and receipt count per project/vendor).
6. Include Worker/User Breakdown (spend per worker, with per-project split if available).
7. Include Category Breakdown (Materials, Equipment, Fuel, etc.).
8. If no matching records exist, clearly state: "No receipt records match your filter criteria."
9. Structure clearly with clean Markdown headers and bullet points.
10. Do NOT expose internal function names or debug code.
"""
        answer = _gemini_call(sys_prompt)
        if not answer:
            if financial_payload["receipt_count"] == 0:
                answer = (
                    f"**Financial Expense Report — {financial_payload['date_period']}**\n\n"
                    f"• **Total Spend**: **$0.00 USD** (0 receipts verified)\n\n"
                    f"No receipt records match your filter criteria."
                )
            else:
                lines = [
                    f"**Financial Expense Report — {financial_payload['date_period']}**\n",
                    f"• **Total Spend**: **${financial_payload['total_spend_usd']:,.2f} USD** ({financial_payload['receipt_count']} receipts verified)\n",
                    "**Project Breakdown:**"
                ]
                for p in financial_payload["projects_breakdown"]:
                    lines.append(f"• {p['project_name']}: ${p['total_spend']:,.2f} ({p['receipt_count']} receipts)")
                lines.append("\n**Worker Breakdown:**")
                for w in financial_payload["workers_breakdown"]:
                    lines.append(f"• {w['worker_name']}: ${w['total_spend']:,.2f}")
                lines.append("\n**Category Breakdown:**")
                for c in financial_payload["categories_breakdown"]:
                    lines.append(f"• {c['category']}: ${c['total_spend']:,.2f}")
                answer = "\n".join(lines)
        return {"answer": answer, "intent": "expense_report", "auto_approved_leave": False}

    # ------------------------------------------------------------------
    # 3. HISTORICAL PROJECT DATABASE SEARCH AGENT (Admin Only)
    # ------------------------------------------------------------------
    project_keywords = [
        "past project", "historical project", "past projects", "project database",
        "projects history", "filter project", "show projects", "project history",
        "show me all", "show all projects", "show past", "list projects",
        "sqft", "covered area", "structural design", "rcc", "steel frame",
        "mat foundation", "steel tonnage", "tons of steel", "floors", "budget"
    ]
    is_project_query = any(k in prompt_lower for k in project_keywords) or session_data.get("last_intent") == "historical_projects"

    if is_project_query:
        session_data["last_intent"] = "historical_projects"

        # Extract project criteria using Gemini & update session context
        curr_proj_ctx = session_manager.get_project_filter_context(sess_id)
        extracted_proj = extract_project_filters_with_gemini(prompt, curr_proj_ctx)
        active_proj_ctx = session_manager.update_project_filter_context(sess_id, extracted_proj)

        # Check if any specific filter criteria are active
        filter_keys = ["min_sqft", "max_sqft", "structural_system", "floors", "foundation_type", "min_steel_tons", "max_steel_tons", "min_budget", "max_budget", "location"]
        has_active_filters = any(active_proj_ctx.get(k) is not None for k in filter_keys)

        # If user asks a vague query without criteria, ask interactively what criteria they want
        if not has_active_filters:
            prompt_words = prompt_lower.split()
            vague_request = len(prompt_words) <= 5 or prompt_lower in ["past project history", "show past projects", "past projects", "project database", "historical projects"]
            if vague_request:
                return {
                    "answer": (
                        "📁 **Buildora Past Projects Database Search**\n\n"
                        "What criteria would you like to filter past projects by?\n\n"
                        "• 📏 **Covered Area** (e.g. *area over 45,000 sqft*)\n"
                        "• 🏗️ **Structural System** (e.g. *Reinforced Concrete, Steel Frame, Wood*)\n"
                        "• 🏢 **Number of Floors** (e.g. *6 floors*)\n"
                        "• 🧱 **Foundation Type** (e.g. *Mat Foundation, Spread Footing*)\n"
                        "• ⚖️ **Steel Tonnage** (e.g. *over 100 tons of steel*)\n"
                        "• 💰 **Budget** (e.g. *under $150,000*)\n"
                        "• 📍 **Location** (e.g. *Texas, California*)\n\n"
                        "*Reply with any criteria or combination to query the database!*"
                    ),
                    "intent": "historical_projects",
                    "auto_approved_leave": False
                }

        # Query database with dynamic parameterized WHERE clauses
        proj_payload = query_historical_projects_db(
            db,
            min_sqft=active_proj_ctx.get("min_sqft"),
            max_sqft=active_proj_ctx.get("max_sqft"),
            structural_system=active_proj_ctx.get("structural_system"),
            floors=active_proj_ctx.get("floors"),
            foundation_type=active_proj_ctx.get("foundation_type"),
            min_steel_tons=active_proj_ctx.get("min_steel_tons"),
            max_steel_tons=active_proj_ctx.get("max_steel_tons"),
            min_budget=active_proj_ctx.get("min_budget"),
            max_budget=active_proj_ctx.get("max_budget"),
            location_filter=active_proj_ctx.get("location")
        )

        sys_prompt = f"""
You are the Buildora Enterprise Admin AI Assistant. User asked: "{prompt}"

Live Dynamic Projects Database Query Payload:
{json.dumps(proj_payload, indent=2)}

Instructions:
1. Present the matching projects dynamically based on the exact results in the payload.
2. List the active filters applied under a **Active Query Filters** section (e.g., Area > 45,000 sqft, Steel > 100 Tons).
3. State the total matching projects found count (e.g., "Found 3 matching project(s)").
4. For each matching project, format a clear section/bullet displaying:
   - Project Name & Location
   - Covered Area (sqft) & Floors
   - Structural System & Foundation Type
   - Steel Tonnage Used
   - Total Cost / Budget ($USD)
5. If matching_count is 0, state: "No past projects matched your filter criteria in the database."
6. Do NOT expose internal tool names or debug JSON.
"""
        answer = _gemini_call(sys_prompt)
        if not answer:
            lines = [f"📁 **Past Projects Database Query Results** ({proj_payload['matching_count']} found):\n"]
            for p in proj_payload["projects"]:
                lines.append(
                    f"• **{p['name']}** ({p['location']})\n"
                    f"  Area: {p['sqft']:,} sqft | Floors: {p['floors']} | System: {p['structural_system']} | Foundation: {p['foundation_type']}\n"
                    f"  Steel Tonnage: **{p['steel_tons_used']} Tons** | Budget: **${p['cost_usd']:,.2f} USD**\n"
                )
            answer = "\n".join(lines)
        return {"answer": answer, "intent": "historical_projects", "auto_approved_leave": False}

    # ------------------------------------------------------------------
    # DEFAULT ADMIN FALLBACK — Gemini general answer
    # ------------------------------------------------------------------
    sys_prompt = (
        f'You are the Buildora Enterprise Admin AI Assistant. User asked: "{prompt}"\n'
        'You can assist with: 1) Past Project History, 2) Financial Expense Reports, 3) Steel Takeoff Estimation.\n'
        'Provide a helpful, concise response. Do not expose internal tool names.'
    )
    answer = _gemini_call(sys_prompt)
    if not answer:
        answer = (
            "Hello! I am your Buildora Enterprise Admin AI Assistant.\n\n"
            "I can help you with:\n"
            "1. 📁 **Past Project History** — Filter and search 25+ past projects by area, budget, location\n"
            "2. 📊 **Financial Expense Reports** — Daily, Weekly, Monthly, or custom date-range breakdowns\n"
            "3. 🏗️ **Steel Takeoff Estimation** — Interactive 6-step project input → live market pricing → cost estimate"
        )
    return {"answer": answer, "intent": "general", "auto_approved_leave": False}


def query_hr_assistant(prompt: str, policy_docs: List[Dict[str, str]], leave_balance: int) -> Dict[str, Any]:
    """Compatibility wrapper."""
    return process_unified_ai_assistant_query(prompt, None)
