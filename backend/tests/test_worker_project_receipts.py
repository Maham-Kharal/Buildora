import pytest
from unittest.mock import patch
from io import BytesIO
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.database import SessionLocal, init_db
from backend.core.security import create_access_token
from backend.db.models import User, ActiveProject, ProjectMember, Receipt, ReceiptItem

client = TestClient(app)

WORKER_A_ID = 101
WORKER_B_ID = 102
ADMIN_USER_ID = 103

def get_auth_header(role: str = "WORKER", user_id: int = WORKER_A_ID):
    token = create_access_token(subject=str(user_id), role=role)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(autouse=True)
def setup_test_environment():
    init_db()
    db = SessionLocal()

    # Clear memberships for test users to ensure clean state
    db.query(ProjectMember).filter(ProjectMember.user_id.in_([WORKER_A_ID, WORKER_B_ID, 105, 999])).delete(synchronize_session=False)
    db.commit()

    # Create Test Users
    worker_a = db.query(User).filter(User.id == WORKER_A_ID).first()
    if not worker_a:
        worker_a = User(id=WORKER_A_ID, email="worker_a@buildora.com", full_name="Worker A", role="WORKER", password_hash="secret", is_active=True)
        db.add(worker_a)

    worker_b = db.query(User).filter(User.id == WORKER_B_ID).first()
    if not worker_b:
        worker_b = User(id=WORKER_B_ID, email="worker_b@buildora.com", full_name="Worker B", role="WORKER", password_hash="secret", is_active=True)
        db.add(worker_b)

    admin = db.query(User).filter(User.id == ADMIN_USER_ID).first()
    if not admin:
        admin = User(id=ADMIN_USER_ID, email="admin_c3@buildora.com", full_name="Sarah Admin C3", role="ADMIN", password_hash="secret", is_active=True)
        db.add(admin)

    db.commit()

    # Create Projects: P1 (Active), P2 (Active), P3 (Archived)
    p1 = db.query(ActiveProject).filter(ActiveProject.name == "C3 Proj 1 Active").first()
    if not p1:
        p1 = ActiveProject(name="C3 Proj 1 Active", location="Loc 1", sqft=10000, floors=2, structural_system="Steel", status="ACTIVE", created_by=ADMIN_USER_ID)
        db.add(p1)
    
    p2 = db.query(ActiveProject).filter(ActiveProject.name == "C3 Proj 2 Active").first()
    if not p2:
        p2 = ActiveProject(name="C3 Proj 2 Active", location="Loc 2", sqft=20000, floors=4, structural_system="Concrete", status="ACTIVE", created_by=ADMIN_USER_ID)
        db.add(p2)

    p3 = db.query(ActiveProject).filter(ActiveProject.name == "C3 Proj 3 Archived").first()
    if not p3:
        p3 = ActiveProject(name="C3 Proj 3 Archived", location="Loc 3", sqft=15000, floors=3, structural_system="Wood", status="ARCHIVED", created_by=ADMIN_USER_ID)
        db.add(p3)

    db.commit()
    db.refresh(p1)
    db.refresh(p2)
    db.refresh(p3)

    # Assign Worker A to P1 (Active) and P3 (Archived)
    # Assign Worker B to P2 (Active)
    db.add(ProjectMember(project_id=p1.id, user_id=WORKER_A_ID, assigned_by=ADMIN_USER_ID))
    db.add(ProjectMember(project_id=p3.id, user_id=WORKER_A_ID, assigned_by=ADMIN_USER_ID))
    db.add(ProjectMember(project_id=p2.id, user_id=WORKER_B_ID, assigned_by=ADMIN_USER_ID))

    db.commit()
    db.close()
    yield



def test_assigned_projects_endpoint_returns_minimal_assigned_active_projects_only():
    headers_a = get_auth_header(role="WORKER", user_id=WORKER_A_ID)
    res_a = client.get("/api/v1/user/receipts/assigned-projects", headers=headers_a)
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert isinstance(data_a, list)
    # Worker A is assigned to P1 (Active) and P3 (Archived). Only P1 (Active) should appear.
    assert len(data_a) == 1
    assert data_a[0]["name"] == "C3 Proj 1 Active"
    # Verify ONLY id and name are exposed
    assert set(data_a[0].keys()) == {"id", "name"}
    assert "sqft" not in data_a[0]
    assert "floors" not in data_a[0]
    assert "structural_system" not in data_a[0]


def test_worker_assigned_to_two_projects_sees_both():
    db = SessionLocal()
    worker_m = db.query(User).filter(User.id == 105).first()
    if not worker_m:
        worker_m = User(id=105, email="multi@buildora.com", full_name="Multi Worker", role="WORKER", password_hash="secret", is_active=True)
        db.add(worker_m)
        db.commit()

    p1 = db.query(ActiveProject).filter(ActiveProject.name == "C3 Proj 1 Active").first()
    p2 = db.query(ActiveProject).filter(ActiveProject.name == "C3 Proj 2 Active").first()

    pm1 = db.query(ProjectMember).filter(ProjectMember.project_id == p1.id, ProjectMember.user_id == 105).first()
    if not pm1:
        db.add(ProjectMember(project_id=p1.id, user_id=105, assigned_by=ADMIN_USER_ID))

    pm2 = db.query(ProjectMember).filter(ProjectMember.project_id == p2.id, ProjectMember.user_id == 105).first()
    if not pm2:
        db.add(ProjectMember(project_id=p2.id, user_id=105, assigned_by=ADMIN_USER_ID))

    db.commit()
    db.close()

    headers_m = get_auth_header(role="WORKER", user_id=105)
    res_m = client.get("/api/v1/user/receipts/assigned-projects", headers=headers_m)
    assert res_m.status_code == 200
    data_m = res_m.json()
    assert len(data_m) == 2


def test_worker_assigned_to_zero_projects_gets_empty_list():
    # Create unassigned user safely
    db = SessionLocal()
    unassigned = db.query(User).filter(User.email == "unassigned@buildora.com").first()
    if not unassigned:
        unassigned = User(id=999, email="unassigned@buildora.com", full_name="Unassigned Worker", role="WORKER", password_hash="secret", is_active=True)
        db.add(unassigned)
        db.commit()
        db.refresh(unassigned)
    u_id = unassigned.id
    db.close()

    headers = get_auth_header(role="WORKER", user_id=u_id)
    res = client.get("/api/v1/user/receipts/assigned-projects", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


@patch("backend.modules.user.receipt_submission.service.parse_receipt_with_gemini")
@patch("backend.modules.user.receipt_submission.service.save_uploaded_file")
def test_successful_receipt_upload_stores_project_id(mock_save_file, mock_gemini_ocr):
    mock_save_file.return_value = "/uploads/receipt_images/test_receipt.jpg"
    mock_gemini_ocr.return_value = {
        "vendor_name": "Home Depot Pro",
        "total_amount": 149.99,
        "purchase_date": "2026-09-25",
        "category": "Materials",
        "items": [{"name": "Rebar #4", "quantity": 10.0, "unit_price": 14.99, "total_price": 149.99}]
    }

    db = SessionLocal()
    p1 = db.query(ActiveProject).filter(ActiveProject.name == "C3 Proj 1 Active").first()
    p1_id = p1.id
    db.close()

    headers = get_auth_header(role="WORKER", user_id=WORKER_A_ID)
    dummy_file = ("receipt.jpg", BytesIO(b"fake image data"), "image/jpeg")

    res = client.post(
        "/api/v1/user/receipts/upload",
        headers=headers,
        data={"project_id": p1_id},
        files={"file": dummy_file}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == p1_id
    assert data["project_name"] == "C3 Proj 1 Active"
    assert data["vendor_name"] == "Home Depot Pro"

    # Verify DB persistence
    db = SessionLocal()
    rec = db.query(Receipt).filter(Receipt.id == data["id"]).first()
    assert rec is not None
    assert rec.project_id == p1_id
    assert rec.project.name == "C3 Proj 1 Active"
    db.close()


@patch("backend.modules.user.receipt_submission.service.parse_receipt_with_gemini")
@patch("backend.modules.user.receipt_submission.service.save_uploaded_file")
def test_unassigned_or_forged_project_id_rejected_before_ocr_or_file_storage(mock_save_file, mock_gemini_ocr):
    db = SessionLocal()
    p2 = db.query(ActiveProject).filter(ActiveProject.name == "C3 Proj 2 Active").first()
    p2_id = p2.id  # Worker A is NOT assigned to P2
    db.close()

    headers = get_auth_header(role="WORKER", user_id=WORKER_A_ID)
    dummy_file = ("forged.jpg", BytesIO(b"fake image data"), "image/jpeg")

    res = client.post(
        "/api/v1/user/receipts/upload",
        headers=headers,
        data={"project_id": p2_id},
        files={"file": dummy_file}
    )
    assert res.status_code == 403
    assert "Forbidden" in res.json()["detail"]

    # PROOF: Neither storage nor OCR function was called!
    mock_save_file.assert_not_called()
    mock_gemini_ocr.assert_not_called()


@patch("backend.modules.user.receipt_submission.service.parse_receipt_with_gemini")
@patch("backend.modules.user.receipt_submission.service.save_uploaded_file")
def test_archived_assigned_project_rejected(mock_save_file, mock_gemini_ocr):
    db = SessionLocal()
    p3 = db.query(ActiveProject).filter(ActiveProject.name == "C3 Proj 3 Archived").first()
    p3_id = p3.id  # Worker A is assigned to P3, but P3 is ARCHIVED
    db.close()

    headers = get_auth_header(role="WORKER", user_id=WORKER_A_ID)
    dummy_file = ("receipt.jpg", BytesIO(b"fake image data"), "image/jpeg")

    res = client.post(
        "/api/v1/user/receipts/upload",
        headers=headers,
        data={"project_id": p3_id},
        files={"file": dummy_file}
    )
    assert res.status_code == 403
    mock_save_file.assert_not_called()
    mock_gemini_ocr.assert_not_called()


@patch("backend.modules.user.receipt_submission.service.parse_receipt_with_gemini")
@patch("backend.modules.user.receipt_submission.service.save_uploaded_file")
def test_nonexistent_project_id_rejected(mock_save_file, mock_gemini_ocr):
    headers = get_auth_header(role="WORKER", user_id=WORKER_A_ID)
    dummy_file = ("receipt.jpg", BytesIO(b"fake image data"), "image/jpeg")

    res = client.post(
        "/api/v1/user/receipts/upload",
        headers=headers,
        data={"project_id": 999999},
        files={"file": dummy_file}
    )
    assert res.status_code == 403
    mock_save_file.assert_not_called()
    mock_gemini_ocr.assert_not_called()


def test_upload_missing_project_id_returns_422():
    headers = get_auth_header(role="WORKER", user_id=WORKER_A_ID)
    dummy_file = ("receipt.jpg", BytesIO(b"fake image data"), "image/jpeg")

    res = client.post(
        "/api/v1/user/receipts/upload",
        headers=headers,
        files={"file": dummy_file}
    )
    assert res.status_code == 422


def test_legacy_receipt_without_project_id_remains_readable():
    db = SessionLocal()
    legacy_rec = Receipt(
        user_id=WORKER_A_ID,
        project_id=None,
        image_url="/uploads/legacy.jpg",
        vendor_name="Legacy Supplier",
        total_amount=50.0,
        status="APPROVED"
    )
    db.add(legacy_rec)
    db.commit()
    db.refresh(legacy_rec)
    legacy_id = legacy_rec.id
    db.close()

    headers = get_auth_header(role="WORKER", user_id=WORKER_A_ID)
    res = client.get("/api/v1/user/receipts/my-receipts", headers=headers)
    assert res.status_code == 200
    my_receipts = res.json()
    match = next((r for r in my_receipts if r["id"] == legacy_id), None)
    assert match is not None
    assert match["project_id"] is None
    assert match["project_name"] is None


def test_admin_receipt_monitoring_includes_project_id_and_name():
    db = SessionLocal()
    p1 = db.query(ActiveProject).filter(ActiveProject.name == "C3 Proj 1 Active").first()
    p1_id = p1.id
    rec = Receipt(
        user_id=WORKER_A_ID,
        project_id=p1_id,
        image_url="/uploads/admin_test.jpg",
        vendor_name="Admin Monitored Vendor",
        total_amount=250.0,
        status="PENDING"
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    rec_id = rec.id
    db.close()

    admin_headers = get_auth_header(role="ADMIN", user_id=ADMIN_USER_ID)
    res = client.get("/api/v1/admin/receipts", headers=admin_headers)
    assert res.status_code == 200
    monitored = res.json()
    match = next((r for r in monitored if r["id"] == rec_id), None)
    assert match is not None
    assert match["project_id"] == p1_id
    assert match["project_name"] == "C3 Proj 1 Active"

