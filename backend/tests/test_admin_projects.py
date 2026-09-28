import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.database import SessionLocal
from backend.core.security import create_access_token
from backend.db.models import ActiveProject, ProjectMember, AuditLog, User

client = TestClient(app)

ADMIN_USER_ID = 2
WORKER_USER_ID = 5


def get_auth_header(role: str = "ADMIN", user_id: int = ADMIN_USER_ID):
    token = create_access_token(subject=str(user_id), role=role)
    return {"Authorization": f"Bearer {token}"}


from backend.core.database import engine, Base, SessionLocal

@pytest.fixture(autouse=True)
def setup_test_users():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    admin = db.query(User).filter(User.id == ADMIN_USER_ID).first()
    if not admin:
        admin = User(
            id=ADMIN_USER_ID,
            email="admin_test@buildora.com",
            full_name="Sarah Admin",
            role="ADMIN",
            password_hash="hashed_secret",
            is_active=True,
        )
        db.add(admin)

    worker = db.query(User).filter(User.id == WORKER_USER_ID).first()
    if not worker:
        worker = User(
            id=WORKER_USER_ID,
            email="worker_test@buildora.com",
            full_name="John Worker",
            role="WORKER",
            password_hash="hashed_secret",
            is_active=True,
        )
        db.add(worker)

    db.commit()
    db.close()
    yield


def test_worker_rbac_rejections():
    """Verify WORKER role gets 403 on all admin project endpoints."""
    worker_headers = get_auth_header(role="WORKER", user_id=WORKER_USER_ID)

    res_get = client.get("/api/v1/admin/projects", headers=worker_headers)
    assert res_get.status_code == 403

    res_post = client.post(
        "/api/v1/admin/projects",
        headers=worker_headers,
        json={
            "name": "Unauthorized Proj",
            "location": "Miami, FL",
            "sqft": 10000,
            "floors": 2,
            "structural_system": "Steel",
            "member_ids": [5],
        },
    )
    assert res_post.status_code == 403

    res_assignable = client.get(
        "/api/v1/admin/projects/assignable-users", headers=worker_headers
    )
    assert res_assignable.status_code == 403


def test_list_projects():
    headers = get_auth_header()
    response = client.get("/api/v1/admin/projects", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_assignable_users_endpoint():
    headers = get_auth_header()
    response = client.get(
        "/api/v1/admin/projects/assignable-users", headers=headers
    )
    assert response.status_code == 200
    users = response.json()
    assert isinstance(users, list)
    assert len(users) >= 2
    for u in users:
        assert "id" in u
        assert "full_name" in u
        assert "email" in u
        assert "role" in u
        assert "is_active" in u
        assert "password_hash" not in u


def test_create_project_with_deduplicated_member_ids():
    headers = get_auth_header()
    payload = {
        "name": "Test Austin Tower",
        "location": "Austin, TX",
        "sqft": 45000.0,
        "floors": 6,
        "structural_system": "Reinforced Concrete Frame",
        "member_ids": [2, 5, 5],
    }
    response = client.post(
        "/api/v1/admin/projects", headers=headers, json=payload
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["name"] == "Test Austin Tower"
    assert res_data["location"] == "Austin, TX"
    assert res_data["sqft"] == 45000.0
    assert res_data["floors"] == 6
    assert res_data["status"] == "ACTIVE"
    # Deduplicated 2,5,5 -> exactly two ProjectMember objects
    assert len(res_data["members"]) == 2

    # Verify DB records
    db = SessionLocal()
    proj_id = res_data["id"]
    pms = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == proj_id)
        .all()
    )
    assert len(pms) == 2

    audit = (
        db.query(AuditLog)
        .filter(AuditLog.action == "PROJECT_CREATED")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert audit is not None
    assert "Test Austin Tower" in audit.details
    db.close()


def test_create_project_invalid_member_id_aborts_transaction():
    headers = get_auth_header()
    payload = {
        "name": "Invalid Proj Should Abort",
        "location": "Houston, TX",
        "sqft": 30000.0,
        "floors": 4,
        "structural_system": "Precast Concrete System",
        "member_ids": [2, 9999],
    }
    response = client.post(
        "/api/v1/admin/projects", headers=headers, json=payload
    )
    assert response.status_code == 400

    # Verify nothing persisted to database
    db = SessionLocal()
    proj = (
        db.query(ActiveProject)
        .filter(ActiveProject.name == "Invalid Proj Should Abort")
        .first()
    )
    assert proj is None

    audit = (
        db.query(AuditLog)
        .filter(AuditLog.details.contains("Invalid Proj Should Abort"))
        .first()
    )
    assert audit is None
    db.close()


def test_archive_project_preserves_memberships():
    headers = get_auth_header()
    # Create project first
    payload = {
        "name": "Project to Archive",
        "location": "Dallas, TX",
        "sqft": 20000.0,
        "floors": 3,
        "structural_system": "Steel Frame",
        "member_ids": [2, 5],
    }
    create_resp = client.post(
        "/api/v1/admin/projects", headers=headers, json=payload
    )
    assert create_resp.status_code == 200
    proj_id = create_resp.json()["id"]

    del_resp = client.delete(
        f"/api/v1/admin/projects/{proj_id}", headers=headers
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["detail"] == "Project archived successfully"

    # Verify project status is ARCHIVED in DB and ProjectMember rows are preserved
    db = SessionLocal()
    archived = (
        db.query(ActiveProject).filter(ActiveProject.id == proj_id).first()
    )
    assert archived.status == "ARCHIVED"

    pms = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == proj_id)
        .all()
    )
    assert len(pms) == 2

    audit = (
        db.query(AuditLog)
        .filter(AuditLog.action == "PROJECT_ARCHIVED")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert audit is not None
    assert "Project to Archive" in audit.details
    db.close()


def test_relational_membership_authoritative_no_legacy_column():
    """Verify ActiveProject has no members column and ProjectMember relationship is authoritative."""
    assert not hasattr(ActiveProject, "members")

    headers = get_auth_header()
    db = SessionLocal()
    proj = ActiveProject(
        name="Relational Test Project",
        location="Chicago, IL",
        sqft=15000.0,
        floors=2,
        structural_system="Wood Frame",
        status="ACTIVE",
        created_by=ADMIN_USER_ID,
    )
    db.add(proj)
    db.flush()
    pm = ProjectMember(project_id=proj.id, user_id=WORKER_USER_ID, assigned_by=ADMIN_USER_ID)
    db.add(pm)
    db.commit()
    proj_id = proj.id
    db.close()

    res = client.get("/api/v1/admin/projects", headers=headers)
    assert res.status_code == 200
    projects = res.json()
    match = next((p for p in projects if p["id"] == proj_id), None)
    assert match is not None
    assert len(match["members"]) == 1
    assert match["members"][0]["user_id"] == WORKER_USER_ID


def test_archive_nonexistent_project_returns_404():
    headers = get_auth_header()
    del_resp = client.delete("/api/v1/admin/projects/999999", headers=headers)
    assert del_resp.status_code == 404

