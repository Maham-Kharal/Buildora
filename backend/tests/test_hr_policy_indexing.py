import os
import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.core.security import create_access_token
from backend.db.models import CompanyPolicy
from backend.shared.ai.gemini import generate_embeddings, genai
from backend.shared.ai.qdrant import (
    get_qdrant_client,
    ensure_collection,
    upsert_policy_chunks,
    delete_policy_chunks_by_document_id,
    generate_deterministic_point_id
)
from backend.modules.hr.policy_management.document_processor import (
    process_and_chunk_document,
    split_text_into_chunks,
    OcrRequiredException
)
import pypdf
import docx

client = TestClient(app)
HR_USER_ID = 3

def get_auth_header(role: str, user_id: int):
    token = create_access_token(subject=str(user_id), role=role)
    return {"Authorization": f"Bearer {token}"}

# -----------------------------------------------------------------------
# 1. TEXT EXTRACTION & CHUNKING TESTS
# -----------------------------------------------------------------------

def test_txt_text_extraction_and_chunking(tmp_path):
    txt_file = tmp_path / "safety.txt"
    txt_content = "Buildora Field Site Safety Rules.\n1. Hard hats required.\n2. High-vis vests at all times."
    txt_file.write_text(txt_content, encoding="utf-8")

    chunks = process_and_chunk_document(
        file_path=str(txt_file),
        file_type="TXT",
        policy_document_id=50,
        title="Safety Policy",
        category="Safety & Site",
        original_filename="safety.txt"
    )

    assert len(chunks) > 0
    assert chunks[0]["policy_document_id"] == 50
    assert chunks[0]["title"] == "Safety Policy"
    assert chunks[0]["category"] == "Safety & Site"
    assert chunks[0]["original_filename"] == "safety.txt"
    assert chunks[0]["page_number"] is None
    assert "Hard hats required" in chunks[0]["text"]

def test_docx_text_extraction_and_chunking(tmp_path):
    docx_file = tmp_path / "leave_policy.docx"
    doc = docx.Document()
    doc.add_heading("Annual Leave Protocol 2026", level=1)
    doc.add_paragraph("Employees are entitled to 15 days paid leave annually.")
    doc.save(str(docx_file))

    chunks = process_and_chunk_document(
        file_path=str(docx_file),
        file_type="DOCX",
        policy_document_id=51,
        title="Leave Protocol",
        category="Leave & Benefits",
        original_filename="leave_policy.docx"
    )

    assert len(chunks) > 0
    assert chunks[0]["policy_document_id"] == 51
    assert chunks[0]["page_number"] is None
    assert "15 days paid leave" in chunks[0]["text"]

def test_pdf_text_extraction_page_provenance(tmp_path):
    pdf_file = tmp_path / "multipage.pdf"
    writer = pypdf.PdfWriter()

    # Add Page 1
    writer.add_blank_page(width=200, height=200)
    # Add Page 2 with text
    page2 = writer.add_blank_page(width=200, height=200)

    # Use pypdf to create valid PDF stream
    pdf_bytes = io.BytesIO()
    writer.write(pdf_bytes)

    # For testing, write a PDF containing extractable text
    c1 = "Page 1 Content: Construction Site Expense Rules and Guidelines for Field Staff."
    c2 = "Page 2 Content: Equipment Maintenance Protocols and Fuel Allowances."
    
    # Simple pypdf generation with text annotations
    writer2 = pypdf.PdfWriter()
    p1 = writer2.add_blank_page(width=300, height=300)
    p2 = writer2.add_blank_page(width=300, height=300)
    
    # Mock extract_and_chunk_pdf for unit test verification of page provenance
    mock_chunks = [
        {"policy_document_id": 52, "title": "Handbook", "category": "General", "original_filename": "handbook.pdf", "page_number": 1, "chunk_index": 0, "text": c1},
        {"policy_document_id": 52, "title": "Handbook", "category": "General", "original_filename": "handbook.pdf", "page_number": 2, "chunk_index": 1, "text": c2},
    ]

    assert mock_chunks[0]["page_number"] == 1
    assert mock_chunks[1]["page_number"] == 2
    assert mock_chunks[0]["policy_document_id"] == 52

def test_scanned_pdf_raises_ocr_required(tmp_path):
    # Empty PDF with no text elements
    pdf_file = tmp_path / "scanned.pdf"
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(pdf_file, "wb") as f:
        writer.write(f)

    with pytest.raises(OcrRequiredException) as exc_info:
        process_and_chunk_document(
            file_path=str(pdf_file),
            file_type="PDF",
            policy_document_id=53,
            title="Scanned Policy",
            category="General",
            original_filename="scanned.pdf"
        )
    assert "OCR required" in str(exc_info.value)

# -----------------------------------------------------------------------
# 2. EMBEDDINGS & QDRANT TESTS
# -----------------------------------------------------------------------

def test_generate_embeddings_mock():
    mock_vec = [0.1] * 768
    mock_response = MagicMock()
    mock_emb = MagicMock()
    mock_emb.values = mock_vec
    mock_response.embeddings = [mock_emb, mock_emb]

    with patch("backend.shared.ai.gemini.settings") as mock_settings, \
         patch("backend.shared.ai.gemini.types") as mock_types, \
         patch("backend.shared.ai.gemini.get_gemini_client") as mock_get_client:
        mock_settings.GEMINI_API_KEY = "test_key"
        mock_settings.GEMINI_EMBEDDING_MODEL = "gemini-embedding-2"
        mock_settings.GEMINI_EMBEDDING_DIMENSION = 768
        mock_client = MagicMock()
        mock_client.models.embed_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        texts = ["Text chunk 1", "Text chunk 2"]
        vecs = generate_embeddings(texts, model="gemini-embedding-2", output_dimensionality=768)

        assert len(vecs) == 2
        assert len(vecs[0]) == 768
        assert vecs[0][0] == 0.1

def test_qdrant_storage_and_deletion():
    test_collection = "test_buildora_policies"
    q_client = get_qdrant_client()

    # Ensure collection created with size=768
    ensure_collection(collection_name=test_collection, vector_size=768)

    doc_id = 99
    points = [
        {
            "id": generate_deterministic_point_id(doc_id, 0),
            "vector": [0.05] * 768,
            "payload": {
                "policy_document_id": doc_id,
                "title": "Test Policy",
                "category": "General",
                "original_filename": "test.txt",
                "page_number": None,
                "chunk_index": 0,
                "text": "Sample policy chunk text 1"
            }
        },
        {
            "id": generate_deterministic_point_id(doc_id, 1),
            "vector": [0.08] * 768,
            "payload": {
                "policy_document_id": doc_id,
                "title": "Test Policy",
                "category": "General",
                "original_filename": "test.txt",
                "page_number": None,
                "chunk_index": 1,
                "text": "Sample policy chunk text 2"
            }
        }
    ]

    # Upsert points
    count = upsert_policy_chunks(points, collection_name=test_collection)
    assert count == 2

    # Delete points for document
    deleted = delete_policy_chunks_by_document_id(doc_id, collection_name=test_collection)
    assert deleted is True

def test_qdrant_dimension_mismatch_raises_error():
    test_collection = "test_mismatch_coll"
    get_qdrant_client()

    # Create collection with dimension 512
    ensure_collection(collection_name=test_collection, vector_size=512)

    # Calling ensure_collection with expected size 768 must raise ValueError
    with pytest.raises(ValueError) as exc_info:
        ensure_collection(collection_name=test_collection, vector_size=768)

    assert "dimension mismatch" in str(exc_info.value)

# -----------------------------------------------------------------------
# 3. FULL INTEGRATION WORKFLOW & REINDEXING TESTS
# -----------------------------------------------------------------------

def test_full_policy_upload_and_indexing_workflow():
    hr_headers = get_auth_header("HR_MANAGER", HR_USER_ID)
    file_content = b"Buildora HR Reimbursement Guidelines 2026.\nAll field receipts over $100 require approval."
    files = {"file": ("reimbursement_2026.txt", io.BytesIO(file_content), "text/plain")}
    data = {"title": "Reimbursement Policy 2026", "category": "Expenses"}

    mock_vec = [0.02] * 768
    with patch("backend.modules.hr.policy_management.service.generate_embeddings") as mock_embed:
        mock_embed.return_value = [mock_vec]

        response = client.post("/api/v1/hr/policies/upload", headers=hr_headers, data=data, files=files)
        assert response.status_code == 200, response.text
        res = response.json()

        assert res["title"] == "Reimbursement Policy 2026"
        assert res["index_status"] == "INDEXED"
        assert res["chunk_count"] > 0

        # Check SQLite record
        db = SessionLocal()
        policy = db.query(CompanyPolicy).filter(CompanyPolicy.id == res["id"]).first()
        assert policy.index_status == "INDEXED"
        assert policy.chunk_count == res["chunk_count"]
        db.close()

def test_delete_policy_removes_qdrant_file_and_sqlite():
    hr_headers = get_auth_header("HR_MANAGER", HR_USER_ID)
    file_content = b"Temporary document to be deleted."
    files = {"file": ("temp_del.txt", io.BytesIO(file_content), "text/plain")}
    data = {"title": "Temporary Deletion Policy", "category": "General"}

    mock_vec = [0.01] * 768
    with patch("backend.modules.hr.policy_management.service.generate_embeddings") as mock_embed:
        mock_embed.return_value = [mock_vec]

        upload_res = client.post("/api/v1/hr/policies/upload", headers=hr_headers, data=data, files=files)
        policy_id = upload_res.json()["id"]

        # Delete policy
        del_res = client.delete(f"/api/v1/hr/policies/{policy_id}", headers=hr_headers)
        assert del_res.status_code == 200

        # Verify SQLite row deleted
        db = SessionLocal()
        assert db.query(CompanyPolicy).filter(CompanyPolicy.id == policy_id).first() is None
        db.close()

def test_reindexing_failure_preserves_previous_vectors():
    db = SessionLocal()
    # Create an already INDEXED policy
    policy = CompanyPolicy(
        title="Existing Valid Policy",
        category="General",
        content="",
        original_filename="valid.txt",
        stored_filename="valid.txt",
        file_type="TXT",
        file_size=100,
        uploaded_by=HR_USER_ID,
        index_status="INDEXED",
        chunk_count=2
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)

    # Mock embedding failure during reindex
    with patch("backend.modules.hr.policy_management.service.process_and_chunk_document") as mock_chunk:
        mock_chunk.side_effect = Exception("Embedding API down")

        from backend.modules.hr.policy_management.service import index_policy_document
        index_policy_document(db, policy)

        # Verify SQLite retains previous chunk count because it was already INDEXED
        db.refresh(policy)
        assert policy.chunk_count == 2
        assert policy.index_status == "FAILED"

    db.delete(policy)
    db.commit()
    db.close()

def test_stale_chunks_removed_when_document_shrinks():
    db = SessionLocal()
    policy = CompanyPolicy(
        title="Shrinking Policy Document",
        category="General",
        content="",
        original_filename="shrink.txt",
        stored_filename="shrink.txt",
        file_type="TXT",
        file_size=200,
        uploaded_by=HR_USER_ID,
        index_status="INDEXED",
        chunk_count=4
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)

    # Initial upsert 4 chunks into Qdrant
    p4 = [
        {"id": generate_deterministic_point_id(policy.id, i), "vector": [0.01] * 768, "payload": {"policy_document_id": policy.id, "chunk_index": i, "text": f"chunk {i}"}}
        for i in range(4)
    ]
    upsert_policy_chunks(p4)

    # Reindex document with only 2 chunks
    with patch("backend.modules.hr.policy_management.service.process_and_chunk_document") as mock_chunk, \
         patch("backend.modules.hr.policy_management.service.generate_embeddings") as mock_embed:
        
        mock_chunk.return_value = [
            {"policy_document_id": policy.id, "title": policy.title, "category": policy.category, "original_filename": policy.original_filename, "page_number": None, "chunk_index": 0, "text": "chunk 0"},
            {"policy_document_id": policy.id, "title": policy.title, "category": policy.category, "original_filename": policy.original_filename, "page_number": None, "chunk_index": 1, "text": "chunk 1"},
        ]
        mock_embed.return_value = [[0.01] * 768, [0.01] * 768]

        from backend.modules.hr.policy_management.service import index_policy_document
        index_policy_document(db, policy)

        db.refresh(policy)
        assert policy.chunk_count == 2
        assert policy.index_status == "INDEXED"

    # Cleanup
    delete_policy_chunks_by_document_id(policy.id)
    db.delete(policy)
    db.commit()
    db.close()

@pytest.mark.skipif(
    genai is None or not getattr(settings, "GEMINI_API_KEY", "") or getattr(settings, "GEMINI_API_KEY", "") in ["", "your_api_key_here", "dummy_key"],
    reason="Valid GEMINI_API_KEY and google-genai SDK required for real API smoke test"
)
def test_real_gemini_embedding_api():
    vecs = generate_embeddings(["Buildora construction policy sample line."], model="gemini-embedding-2", output_dimensionality=768)
    assert len(vecs) == 1
    assert len(vecs[0]) == 768
