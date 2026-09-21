from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.db.models import ActiveProject, AuditLog, User

router = APIRouter(prefix="/admin/projects", tags=["Admin — Active Projects"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    location: str
    sqft: float
    floors: int
    structural_system: str
    members: List[str] = []


class ProjectOut(BaseModel):
    id: int
    name: str
    location: str
    sqft: float
    floors: int
    structural_system: str
    members: List[str]
    status: str

    class Config:
        from_attributes = True


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("", response_model=List[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return all active construction projects from the database."""
    projects = db.query(ActiveProject).filter(
        ActiveProject.status == "ACTIVE"
    ).order_by(ActiveProject.created_at.desc()).all()
    return projects


@router.post("", response_model=ProjectOut)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new active construction project and persist it to the database."""
    project = ActiveProject(
        name=payload.name,
        location=payload.location,
        sqft=payload.sqft,
        floors=payload.floors,
        structural_system=payload.structural_system,
        members=payload.members,
        status="ACTIVE",
        created_by=current_user.id,
    )
    db.add(project)

    # Write to audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="PROJECT_CREATED",
        details=f"Active project '{payload.name}' created at {payload.location} ({payload.sqft:,.0f} sqft, {payload.floors} floors)",
        metadata_info={
            "project_name": payload.name,
            "location": payload.location,
            "sqft": payload.sqft,
            "floors": payload.floors,
            "structural_system": payload.structural_system,
            "members": payload.members,
        }
    )
    db.add(audit)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft-delete a project by setting status to ARCHIVED."""
    project = db.query(ActiveProject).filter(ActiveProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.status = "ARCHIVED"
    db.add(AuditLog(
        user_id=current_user.id,
        action="PROJECT_ARCHIVED",
        details=f"Project '{project.name}' archived.",
        metadata_info={"project_id": project_id}
    ))
    db.commit()
    return {"detail": "Project archived successfully"}
