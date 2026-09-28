import os
import io
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.core.security import create_access_token
from backend.db.models import CompanyPolicy
from backend.shared.storage import save_uploaded_file
from fastapi import UploadFile

client = TestClient(app)

HR_USER_ID = 3
ADMIN_USER_ID = 2
WORKER_USER_ID = 1

def get_auth_header(role: str, user_id: int):
    token = create_access_token(subject=str(user_id), role=role)
    return {"Authorization": f"Bearer {token}"}

def test_hr_manager_can_upload_pdf():
    hr_headers = get_auth_header("HR_MANAGER", HR_USER_ID)
    file_content = b"%PDF-1.4 sample pdf content for policy document"
    files = {"file": ("safety_guide.pdf", io.BytesIO(file_content), "application/pdf")}
    data = {"title": "Field Site Safety Manual 2026", "category": "Safety & Site"}

    response = client.post("/api/v1/hr/policies/upload", headers=hr_headers, data=data, files=files)
    assert response.status_code == 200, response.text
    res_data = response.json()

    assert res_data["title"] == "Field Site Safety Manual 2026"
    assert res_data["category"] == "Safety & Site"
    assert res_data["original_filename"] == "safety_guide.pdf"
    assert res_data["file_type"] == "PDF"
    assert res_data["file_size"] == len(file_content)
    assert res_data["index_status"] in ["UPLOADED", "INDEXED", "OCR_REQUIRED"]

    # Verify file existence on disk & SQLite record
    db = SessionLocal()
    policy_row = db.query(CompanyPolicy).filter(CompanyPolicy.id == res_data["id"]).first()
    assert policy_row is not None
    assert policy_row.original_filename == "safety_guide.pdf"
    assert policy_row.uploaded_by == HR_USER_ID
    
    stored_filepath = os.path.join(settings.POLICY_UPLOAD_DIR, policy_row.stored_filename)
    assert os.path.exists(stored_filepath)
    db.close()

def test_admin_can_upload_docx():
    admin_headers = get_auth_header("ADMIN", ADMIN_USER_ID)
    file_content = b"DOCX binary placeholder data for leave policy document"
    files = {"file": ("leave_policy.docx", io.BytesIO(file_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"title": "Annual Leave Protocol", "category": "Leave & Benefits"}

    response = client.post("/api/v1/hr/policies/upload", headers=admin_headers, data=data, files=files)
    assert response.status_code == 200, response.text
    res_data = response.json()
    assert res_data["original_filename"] == "leave_policy.docx"
    assert res_data["file_type"] == "DOCX"

def test_upload_txt_file():
    hr_headers = get_auth_header("HR_MANAGER", HR_USER_ID)
    file_content = b"General expense reimbursement rules text content"
    files = {"file": ("expense_rules.txt", io.BytesIO(file_content), "text/plain")}
    data = {"title": "Expense Guidelines", "category": "Expenses"}

    response = client.post("/api/v1/hr/policies/upload", headers=hr_headers, data=data, files=files)
    assert response.status_code == 200
    assert response.json()["file_type"] == "TXT"

def test_worker_cannot_upload():
    worker_headers = get_auth_header("WORKER", WORKER_USER_ID)
    files = {"file": ("test.pdf", io.BytesIO(b"%PDF content"), "application/pdf")}
    data = {"title": "Unauthorized Policy", "category": "General"}

    response = client.post("/api/v1/hr/policies/upload", headers=worker_headers, data=data, files=files)
    assert response.status_code == 403

def test_invalid_extension_rejected():
    hr_headers = get_auth_header("HR_MANAGER", HR_USER_ID)
    files = {"file": ("malicious.exe", io.BytesIO(b"binary"), "application/octet-stream")}
    data = {"title": "Invalid File Policy", "category": "General"}

    response = client.post("/api/v1/hr/policies/upload", headers=hr_headers, data=data, files=files)
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]

def test_oversized_file_rejected():
    hr_headers = get_auth_header("HR_MANAGER", HR_USER_ID)
    huge_content = b"X" * (11 * 1024 * 1024)  # 11 MB
    files = {"file": ("huge.pdf", io.BytesIO(huge_content), "application/pdf")}
    data = {"title": "Huge Document", "category": "General"}

    response = client.post("/api/v1/hr/policies/upload", headers=hr_headers, data=data, files=files)
    assert response.status_code == 400
    assert "File size exceeds" in response.json()["detail"]

def test_list_policies():
    worker_headers = get_auth_header("WORKER", WORKER_USER_ID)
    response = client.get("/api/v1/hr/policies", headers=worker_headers)
    assert response.status_code == 200
    policies = response.json()
    assert isinstance(policies, list)
    assert len(policies) >= 3

def test_delete_policy_document():
    hr_headers = get_auth_header("HR_MANAGER", HR_USER_ID)
    # Upload temporary document to delete
    file_content = b"%PDF content to delete"
    files = {"file": ("temp_doc.pdf", io.BytesIO(file_content), "application/pdf")}
    data = {"title": "Temporary Policy Document", "category": "General"}

    upload_res = client.post("/api/v1/hr/policies/upload", headers=hr_headers, data=data, files=files)
    policy_id = upload_res.json()["id"]

    db = SessionLocal()
    policy_row = db.query(CompanyPolicy).filter(CompanyPolicy.id == policy_id).first()
    stored_path = os.path.join(settings.POLICY_UPLOAD_DIR, policy_row.stored_filename)
    assert os.path.exists(stored_path)
    db.close()

    # Delete policy
    del_res = client.delete(f"/api/v1/hr/policies/{policy_id}", headers=hr_headers)
    assert del_res.status_code == 200

    # Verify DB metadata row removed
    db = SessionLocal()
    assert db.query(CompanyPolicy).filter(CompanyPolicy.id == policy_id).first() is None
    db.close()

    # Verify stored file deleted from disk
    assert not os.path.exists(stored_path)

def test_receipt_storage_unaffected():
    # Verify save_uploaded_file still works for receipt images
    mock_file = UploadFile(filename="receipt_test.jpg", file=io.BytesIO(b"fake receipt image content"))
    receipt_url = save_uploaded_file(mock_file)
    assert receipt_url.startswith("/uploads/receipt_images/")
    file_name = os.path.basename(receipt_url)
    assert os.path.exists(os.path.join(settings.UPLOAD_DIR, file_name))
