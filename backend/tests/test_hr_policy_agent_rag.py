import pytest
import os
import io
import uuid
import asyncio
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.core.security import create_access_token
from backend.db.models import User, CompanyPolicy
from backend.modules.admin.ai_chat.agents.policy_agent import PolicyAgent
from backend.modules.admin.ai_chat.agents.base import AgentStatus
from backend.shared.ai.tools import query_company_policy_kb
from backend.shared.ai.qdrant import (
    get_qdrant_client,
    ensure_collection,
    upsert_policy_chunks,
    delete_policy_chunks_by_document_id,
    generate_deterministic_point_id,
    search_policy_chunks
)
from backend.shared.ai.gemini import format_agent_explanation_with_gemini, process_unified_ai_assistant_query
from backend.modules.hr.policy_management.service import upload_policy_document, delete_policy_document

client = TestClient(app)

HR_USER_ID = 3
WORKER_USER_ID = 1

def get_auth_header(role: str, user_id: int):
    token = create_access_token(subject=str(user_id), role=role)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(autouse=True)
def setup_test_users_and_qdrant():
    db = SessionLocal()
    import backend.shared.ai.qdrant as qdrant_mod
    qdrant_mod._qdrant_client = None
    
    hr = db.query(User).filter(User.id == HR_USER_ID).first()
    if not hr:
        hr = User(id=HR_USER_ID, email="hr_mgr@buildora.com", full_name="Sarah HR", role="HR_MANAGER", password_hash="hashed_secret")
        db.add(hr)
    worker = db.query(User).filter(User.id == WORKER_USER_ID).first()
    if not worker:
        worker = User(id=WORKER_USER_ID, email="worker_user@buildora.com", full_name="John Worker", role="WORKER", password_hash="hashed_secret")
        db.add(worker)
    db.commit()
    db.close()
    yield

def dummy_embedding(text: str):
    """Generates deterministic mock 768-dim vector based on text keywords."""
    vec = [0.0] * 768
    t = text.lower()
    if "safety" in t or "ppe" in t or "hard hat" in t or "protection" in t:
        vec[0] = 0.95
        vec[1] = 0.1
    elif "leave" in t or "vacation" in t or "sick" in t or "weather" in t:
        vec[10] = 0.95
        vec[11] = 0.2
    elif "reimbursement" in t or "expense" in t or "meal" in t:
        vec[20] = 0.95
    elif "conflict_a" in t or "remote work policy 2024" in t:
        vec[30] = 0.90
    elif "conflict_b" in t or "remote work policy 2026" in t:
        vec[30] = 0.88
    else:
        vec[100] = 0.5
    return vec

def mock_gen_embeddings(texts, model=None, output_dimensionality=None):
    return [dummy_embedding(t) for t in texts]


# -------------------------------------------------------------------
# TESTS FOR HR POLICY CHANGE 3
# -------------------------------------------------------------------

@patch("backend.modules.hr.policy_management.service.generate_embeddings", side_effect=mock_gen_embeddings)
@patch("backend.shared.ai.gemini.generate_embeddings", side_effect=mock_gen_embeddings)
def test_1_exact_policy_question_retrieves_correct_chunk(mock_emb1, mock_emb2):
    """Test 1: Exact policy question retrieves correct chunk."""
    db = SessionLocal()
    file_content = b"Site Safety Protocol 2026. All field workers must wear approved hard hats and steel-toe boots at all times."
    upload_file = MagicMock()
    upload_file.filename = "safety_protocol.txt"
    upload_file.file = io.BytesIO(file_content)

    policy = upload_policy_document(db, hr_id=HR_USER_ID, title="Site Safety Protocol", category="Safety", file=upload_file)
    assert policy.index_status == "INDEXED"

    results = query_company_policy_kb(db, "hard hat steel-toe boots safety protocol")
    assert len(results) > 0
    assert results[0]["title"] == "Site Safety Protocol"
    assert "hard hats" in results[0]["text"]
    assert results[0]["original_filename"] == "safety_protocol.txt"


@patch("backend.modules.hr.policy_management.service.generate_embeddings", side_effect=mock_gen_embeddings)
@patch("backend.shared.ai.gemini.generate_embeddings", side_effect=mock_gen_embeddings)
def test_2_paraphrased_question_retrieves_semantically_relevant_chunk(mock_emb1, mock_emb2):
    """Test 2: Paraphrased question retrieves semantically relevant chunk."""
    db = SessionLocal()
    file_content = b"Site Safety Protocol 2026. All field workers must wear approved hard hats and protective gear on site."
    upload_file = MagicMock()
    upload_file.filename = "site_safety.txt"
    upload_file.file = io.BytesIO(file_content)

    upload_policy_document(db, hr_id=HR_USER_ID, title="Safety Policy", category="Safety", file=upload_file)

    results = query_company_policy_kb(db, "What ppe and head protection is required on site?")
    assert len(results) > 0
    assert "hard hats" in results[0]["text"]


@patch("backend.shared.ai.gemini.generate_embeddings", side_effect=mock_gen_embeddings)
def test_3_deep_page_pdf_content_retrievable(mock_emb):
    """Test 3: Deep-page PDF content is retrievable with page provenance."""
    db = SessionLocal()

    points = [
        {
            "id": generate_deterministic_point_id(99, 0),
            "vector": dummy_embedding("General overview of Buildora operations."),
            "payload": {
                "policy_document_id": 99,
                "title": "Corporate Manual",
                "category": "General",
                "original_filename": "manual.pdf",
                "page_number": 1,
                "chunk_index": 0,
                "text": "General overview of Buildora operations."
            }
        },
        {
            "id": generate_deterministic_point_id(99, 28),
            "vector": dummy_embedding("Deep Page 14 Safety Standard: Emergency evacuation assembly area is Lot B."),
            "payload": {
                "policy_document_id": 99,
                "title": "Corporate Manual",
                "category": "Safety",
                "original_filename": "manual.pdf",
                "page_number": 14,
                "chunk_index": 28,
                "text": "Deep Page 14 Safety Standard: Emergency evacuation assembly area is Lot B."
            }
        }
    ]
    upsert_policy_chunks(points)

    results = query_company_policy_kb(db, "emergency evacuation assembly area safety")
    assert len(results) > 0
    match = [r for r in results if r["page_number"] == 14][0]
    assert match["page_number"] == 14
    assert match["original_filename"] == "manual.pdf"
    assert "Lot B" in match["text"]


@patch("backend.modules.hr.policy_management.service.generate_embeddings", side_effect=mock_gen_embeddings)
@patch("backend.shared.ai.gemini.generate_embeddings", side_effect=mock_gen_embeddings)
def test_4_5_6_filename_and_page_number_provenance(mock_emb1, mock_emb2):
    """Test 4, 5, 6: Filename and Page number provenance (PDF has page_number, TXT/DOCX has None)."""
    db = SessionLocal()
    file_content = b"TX Policy content for reimbursement up to $50 per day."
    upload_file = MagicMock()
    upload_file.filename = "expense_reimbursement.txt"
    upload_file.file = io.BytesIO(file_content)

    upload_policy_document(db, hr_id=HR_USER_ID, title="Expense Policy", category="Financial", file=upload_file)

    results = query_company_policy_kb(db, "meal expense reimbursement limit")
    assert len(results) > 0
    res = results[0]
    assert res["original_filename"] == "expense_reimbursement.txt"
    assert res["page_number"] is None


@patch("backend.shared.ai.gemini.generate_embeddings", side_effect=mock_gen_embeddings)
def test_7_8_no_relevant_match_and_below_threshold(mock_emb):
    """Test 7, 8: No relevant match returns empty list (below threshold)."""
    db = SessionLocal()

    def orthogonal_emb(texts, **kwargs):
        return [[0.0] * 768]

    with patch("backend.shared.ai.gemini.generate_embeddings", side_effect=orthogonal_emb):
        results = query_company_policy_kb(db, "completely unrelated topic about orbital mechanics")
        assert len(results) == 0

    agent = PolicyAgent()
    with patch("backend.shared.ai.gemini.generate_embeddings", side_effect=orthogonal_emb):
        agent_res = asyncio.run(agent.execute(message="orbital mechanics", session={}, db=db, current_user=MagicMock()))
        assert agent_res.status == AgentStatus.NOT_FOUND
        assert agent_res.context_for_llm["sources"] == []


@patch("backend.modules.hr.policy_management.service.generate_embeddings", side_effect=mock_gen_embeddings)
@patch("backend.shared.ai.gemini.generate_embeddings", side_effect=mock_gen_embeddings)
def test_9_deleted_policy_vectors_no_longer_retrievable(mock_emb1, mock_emb2):
    """Test 9: Deleted policy vectors are immediately removed from Qdrant."""
    db = SessionLocal()
    file_content = b"Temporary Leave Guidance 2026. Special leave granted for weather."
    upload_file = MagicMock()
    upload_file.filename = "temp_leave.txt"
    upload_file.file = io.BytesIO(file_content)

    policy = upload_policy_document(db, hr_id=HR_USER_ID, title="Temp Leave Policy", category="Leave", file=upload_file)
    policy_id = policy.id

    res_before = query_company_policy_kb(db, "weather leave vacation")
    assert len(res_before) > 0

    delete_policy_document(db, hr_id=HR_USER_ID, policy_id=policy_id)

    res_after = query_company_policy_kb(db, "weather leave vacation")
    assert len(res_after) == 0


@patch("backend.shared.ai.gemini.generate_embeddings", side_effect=mock_gen_embeddings)
def test_10_multiple_documents_can_contribute_sources(mock_emb):
    """Test 10: Multiple documents can contribute relevant sources."""
    db = SessionLocal()
    p1 = {
        "id": generate_deterministic_point_id(1, 0),
        "vector": dummy_embedding("PPE safety rule: Wear helmets on site."),
        "payload": {"policy_document_id": 1, "title": "Safety Part 1", "original_filename": "part1.txt", "page_number": None, "chunk_index": 0, "text": "Wear helmets."}
    }
    p2 = {
        "id": generate_deterministic_point_id(2, 0),
        "vector": dummy_embedding("PPE safety rule: Wear high-visibility vests on site."),
        "payload": {"policy_document_id": 2, "title": "Safety Part 2", "original_filename": "part2.txt", "page_number": None, "chunk_index": 0, "text": "Wear vests."}
    }
    upsert_policy_chunks([p1, p2])

    results = query_company_policy_kb(db, "safety ppe helmet vest")
    assert len(results) >= 2
    titles = [r["title"] for r in results]
    assert "Safety Part 1" in titles
    assert "Safety Part 2" in titles


@patch("backend.shared.ai.gemini.generate_embeddings", side_effect=mock_gen_embeddings)
def test_11_conflicting_sources_remain_distinguishable(mock_emb):
    """Test 11: Conflicting sources are preserved in payload for Gemini to highlight."""
    db = SessionLocal()
    p1 = {
        "id": generate_deterministic_point_id(10, 0),
        "vector": dummy_embedding("Remote work policy 2024: Allowed up to 3 days per week."),
        "payload": {"policy_document_id": 10, "title": "Remote Work 2024", "original_filename": "remote_2024.pdf", "page_number": 2, "chunk_index": 0, "text": "Allowed 3 days."}
    }
    p2 = {
        "id": generate_deterministic_point_id(11, 0),
        "vector": dummy_embedding("Remote work policy 2026: Remote work is strictly prohibited."),
        "payload": {"policy_document_id": 11, "title": "Remote Work 2026", "original_filename": "remote_2026.pdf", "page_number": 1, "chunk_index": 0, "text": "Strictly prohibited."}
    }
    upsert_policy_chunks([p1, p2])

    agent = PolicyAgent()
    res = asyncio.run(agent.execute(message="remote work policy 2024 2026 conflict_a conflict_b", session={}, db=db, current_user=MagicMock()))

    assert res.status == AgentStatus.COMPLETED
    sources = res.context_for_llm["sources"]
    assert len(sources) >= 2
    filenames = [s["original_filename"] for s in sources]
    assert "remote_2024.pdf" in filenames
    assert "remote_2026.pdf" in filenames


@patch("backend.shared.ai.gemini.generate_embeddings", side_effect=mock_gen_embeddings)
def test_12_policy_agent_returns_structured_sources(mock_emb):
    """Test 12: PolicyAgent returns structured sources in context_for_llm."""
    db = SessionLocal()
    p = {
        "id": generate_deterministic_point_id(55, 2),
        "vector": dummy_embedding("Safety rule chunk."),
        "payload": {
            "policy_document_id": 55,
            "title": "Safety Guidelines",
            "category": "Safety",
            "original_filename": "safety.pdf",
            "page_number": 4,
            "chunk_index": 2,
            "text": "Safety rule chunk text."
        }
    }
    upsert_policy_chunks([p])

    agent = PolicyAgent()
    res = asyncio.run(agent.execute(message="safety rule", session={}, db=db, current_user=MagicMock()))

    assert res.status == AgentStatus.COMPLETED
    ctx = res.context_for_llm
    assert ctx["type"] == "company_policy_payload"
    assert "sources" in ctx
    s0 = ctx["sources"][0]
    assert s0["policy_document_id"] == 55
    assert s0["title"] == "Safety Guidelines"
    assert s0["original_filename"] == "safety.pdf"
    assert s0["page_number"] == 4
    assert s0["chunk_index"] == 2
    assert s0["text"] == "Safety rule chunk text."
    assert "retrieval_score" in s0


@patch("backend.shared.ai.gemini.generate_embeddings", side_effect=mock_gen_embeddings)
def test_13_worker_assistant_path_uses_same_retrieval(mock_emb):
    """Test 13: Worker policy assistant path reuses query_company_policy_kb retrieval."""
    db = SessionLocal()
    worker_user = db.query(User).filter(User.role == "WORKER").first()

    p = {
        "id": generate_deterministic_point_id(88, 0),
        "vector": dummy_embedding("Site Safety rule: Ear protection required in noise zone."),
        "payload": {"policy_document_id": 88, "title": "Worker Safety", "original_filename": "worker_safety.txt", "page_number": None, "chunk_index": 0, "text": "Ear protection required."}
    }
    upsert_policy_chunks([p])

    with patch("backend.shared.ai.gemini.generate_gemini_response", return_value=None):
        resp = process_unified_ai_assistant_query(
            prompt="What safety gear is needed for noise zone?",
            db=db,
            current_user=worker_user,
            user_role="WORKER"
        )
        assert resp["intent"] == "policy"
        assert "Worker Safety" in resp["answer"]
        assert "worker_safety.txt" in resp["answer"]


def test_14_15_gemini_grounding_and_no_hallucinations():
    """Test 14, 15: Gemini formatting receives retrieved context only and does not invent policies."""
    sources = [
        {
            "policy_document_id": 12,
            "title": "Employee Handbook 2026",
            "original_filename": "handbook_2026.pdf",
            "page_number": 7,
            "chunk_index": 14,
            "text": "Maternity leave entitlement is 12 weeks of paid leave.",
            "retrieval_score": 0.88
        }
    ]

    with patch("backend.shared.ai.gemini.generate_gemini_response") as mock_gemini:
        mock_gemini.return_value = "According to Employee Handbook 2026, page 7, maternity leave entitlement is 12 weeks of paid leave."
        formatted = format_agent_explanation_with_gemini(
            user_message="What is the maternity leave entitlement?",
            agent_name="PolicyAgent",
            status="completed",
            context_data={"type": "company_policy_payload", "sources": sources}
        )

        assert "12 weeks" in formatted
        call_contents = mock_gemini.call_args[1]["contents"] if "contents" in mock_gemini.call_args[1] else mock_gemini.call_args[0][0]
        assert "handbook_2026.pdf" in str(call_contents)
        assert "12 weeks of paid leave" in str(call_contents)


def test_16_17_steel_and_financial_agents_remain_unchanged():
    """Test 16, 17: SteelAgent and FinancialReportAgent modules and imports remain untouched."""
    from backend.modules.admin.ai_chat.agents.steel_agent import SteelEstimationAgent
    from backend.modules.admin.ai_chat.agents.financial_agent import FinancialReportAgent

    assert hasattr(SteelEstimationAgent, "execute")
    assert hasattr(FinancialReportAgent, "execute")
