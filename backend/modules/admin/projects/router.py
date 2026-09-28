from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.deps import require_role
from backend.db.models import User
from backend.modules.admin.projects.schemas import ProjectCreate, ProjectOut, AssignableUserOut
from backend.modules.admin.projects.service import (
    get_all_active_projects,
    create_active_project,
    archive_active_project,
    get_assignable_users,
)

router = APIRouter(prefix="/admin/projects", tags=["Admin — Active Projects"])


@router.get("", response_model=List[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["ADMIN"]))
):
    """Return all active construction projects from the database."""
    return get_all_active_projects(db)


@router.get("/assignable-users", response_model=List[AssignableUserOut])
def list_assignable_users(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["ADMIN"]))
):
    """Return all active users eligible for project team assignment."""
    return get_assignable_users(db)


@router.post("", response_model=ProjectOut)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["ADMIN"]))
):
    """Create a new active construction project and persist it to the database."""
    return create_active_project(db, payload, admin_user)


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["ADMIN"]))
):
    """Soft-delete a project by setting status to ARCHIVED."""
    archive_active_project(db, project_id, admin_user)
    return {"detail": "Project archived successfully"}

