import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.main import app
from backend.core.database import SessionLocal
from backend.db.models import User, ActiveProject, ProjectMember, Receipt, AuditLog
from backend.core.security import get_password_hash, create_access_token

client = TestClient(app)

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_deactivation_and_completion_lifecycle(db_session: Session):
    # Setup test HR manager
    hr_user = db_session.query(User).filter_by(email="test_hr_lifecycle@buildora.com").first()
    if not hr_user:
        hr_user = User(
            email="test_hr_lifecycle@buildora.com",
            full_name="HR Manager Test",
            password_hash=get_password_hash("Password123!"),
            role="HR_MANAGER",
            is_active=True
        )
        db_session.add(hr_user)
        db_session.commit()
        db_session.refresh(hr_user)

    # Setup test Admin
    admin_user = db_session.query(User).filter_by(email="test_admin_lifecycle@buildora.com").first()
    if not admin_user:
        admin_user = User(
            email="test_admin_lifecycle@buildora.com",
            full_name="Admin Test",
            password_hash=get_password_hash("Password123!"),
            role="ADMIN",
            is_active=True
        )
        db_session.add(admin_user)
        db_session.commit()
        db_session.refresh(admin_user)

    # Setup test Worker
    worker_user = db_session.query(User).filter_by(email="worker_lifecycle@buildora.com").first()
    if not worker_user:
        worker_user = User(
            email="worker_lifecycle@buildora.com",
            full_name="Worker Lifecycle",
            password_hash=get_password_hash("Password123!"),
            role="WORKER",
            is_active=True
        )
        db_session.add(worker_user)
        db_session.commit()
        db_session.refresh(worker_user)
    else:
        worker_user.is_active = True
        db_session.commit()

    hr_token = create_access_token(subject=hr_user.id, role="HR_MANAGER")
    admin_token = create_access_token(subject=admin_user.id, role="ADMIN")
    worker_token = create_access_token(subject=worker_user.id, role="WORKER")

    # TEST A: Active worker logs in
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "worker_lifecycle@buildora.com",
        "password": "Password123!"
    })
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()

    # Create Project A (ACTIVE) and assign worker
    proj_a = ActiveProject(
        name="Project A Active Test",
        location="NY",
        sqft=1000.0,
        floors=2,
        structural_system="Steel",
        status="ACTIVE",
        created_by=admin_user.id
    )
    db_session.add(proj_a)
    db_session.commit()
    db_session.refresh(proj_a)

    pm_a = ProjectMember(project_id=proj_a.id, user_id=worker_user.id, assigned_by=admin_user.id)
    db_session.add(pm_a)

    # Create Project B (COMPLETED) and assign worker historically
    proj_b = ActiveProject(
        name="Project B Completed Test",
        location="LA",
        sqft=2000.0,
        floors=4,
        structural_system="RCC",
        status="COMPLETED",
        created_by=admin_user.id
    )
    db_session.add(proj_b)
    db_session.commit()
    db_session.refresh(proj_b)

    pm_b = ProjectMember(project_id=proj_b.id, user_id=worker_user.id, assigned_by=admin_user.id)
    db_session.add(pm_b)

    # Add historical receipt for worker
    receipt = Receipt(
        user_id=worker_user.id,
        project_id=proj_b.id,
        image_url="/uploads/test.jpg",
        vendor_name="Home Depot",
        total_amount=150.0,
        status="APPROVED"
    )
    db_session.add(receipt)
    db_session.commit()

    # TEST H: Active assigned project appears in worker receipt dropdown
    dropdown_resp = client.get(
        "/api/v1/user/receipts/assigned-projects",
        headers={"Authorization": f"Bearer {worker_token}"}
    )
    assert dropdown_resp.status_code == 200
    project_ids = [p["id"] for p in dropdown_resp.json()]
    assert proj_a.id in project_ids
    assert proj_b.id not in project_ids  # Completed project should NOT be in worker dropdown

    # TEST D: Worker appears in assignable users before deactivation
    assignable_resp = client.get(
        "/api/v1/admin/projects/assignable-users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert assignable_resp.status_code == 200
    assignable_ids = [u["id"] for u in assignable_resp.json()]
    assert worker_user.id in assignable_ids

    # TEST B: HR deactivates worker
    deactivate_resp = client.patch(
        f"/api/v1/hr/users/{worker_user.id}/deactivate",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert deactivate_resp.status_code == 200

    # Verify is_active == False
    db_session.refresh(worker_user)
    assert worker_user.is_active is False

    # TEST C: Same worker attempts login (rejected)
    bad_login_resp = client.post("/api/v1/auth/login", json={
        "email": "worker_lifecycle@buildora.com",
        "password": "Password123!"
    })
    assert bad_login_resp.status_code in [400, 401]

    # Old token rejected by get_current_user
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {worker_token}"}
    )
    assert me_resp.status_code == 400

    # TEST D: Deactivated worker no longer appears in assignable-users
    assignable_resp_after = client.get(
        "/api/v1/admin/projects/assignable-users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert assignable_resp_after.status_code == 200
    assignable_ids_after = [u["id"] for u in assignable_resp_after.json()]
    assert worker_user.id not in assignable_ids_after

    # TEST E: Deactivated worker removed from ACTIVE project membership
    pm_a_check = db_session.query(ProjectMember).filter_by(project_id=proj_a.id, user_id=worker_user.id).first()
    assert pm_a_check is None

    # TEST F: Deactivated worker remains on COMPLETED project historical membership
    pm_b_check = db_session.query(ProjectMember).filter_by(project_id=proj_b.id, user_id=worker_user.id).first()
    assert pm_b_check is not None

    # TEST G: Old receipts remain intact
    receipt_check = db_session.query(Receipt).filter_by(user_id=worker_user.id).first()
    assert receipt_check is not None
    assert receipt_check.total_amount == 150.0

    # TEST I: Admin marks project COMPLETED
    status_change_resp = client.patch(
        f"/api/v1/admin/projects/{proj_a.id}/status",
        json={"status": "COMPLETED"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert status_change_resp.status_code == 200
    assert status_change_resp.json()["status"] == "COMPLETED"

    # Test invalid status payload ('banana') is rejected with HTTP 400
    invalid_status_resp = client.patch(
        f"/api/v1/admin/projects/{proj_a.id}/status",
        json={"status": "banana"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert invalid_status_resp.status_code == 400
    assert "Invalid project status" in invalid_status_resp.json()["detail"]

    # TEST K: Completed project remains in Admin project view
    projects_resp = client.get(
        "/api/v1/admin/projects",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert projects_resp.status_code == 200
    all_proj_ids = [p["id"] for p in projects_resp.json()]
    assert proj_a.id in all_proj_ids
    assert proj_b.id in all_proj_ids

    # TEST N: Direct receipt submission to completed project is rejected server-side
    from backend.modules.user.receipt_submission.service import process_and_create_receipt
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as excinfo:
        # Create a mock file
        class DummyFile:
            filename = "test.jpg"
        process_and_create_receipt(db_session, hr_user, DummyFile(), proj_b.id)
    # Teardown: Restore user active status and remove test projects/receipts/users for clean test isolation
    try:
        db_session.query(Receipt).filter(Receipt.user_id == worker_user.id).delete()
        db_session.query(ProjectMember).filter(ProjectMember.user_id == worker_user.id).delete()
        db_session.query(ActiveProject).filter(ActiveProject.name.in_(["Project A Active Test", "Project B Completed Test"])).delete()
        db_session.query(User).filter(User.email.in_(["test_hr_lifecycle@buildora.com", "test_admin_lifecycle@buildora.com", "worker_lifecycle@buildora.com"])).delete()
        db_session.query(User).update({User.is_active: True})
        db_session.commit()
    except Exception:
        db_session.rollback()
