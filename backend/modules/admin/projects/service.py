from typing import List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.db.models import ActiveProject, ProjectMember, AuditLog, User
from backend.modules.admin.projects.schemas import ProjectCreate, ProjectMemberOut


def format_project_out(project: ActiveProject) -> Dict[str, Any]:
    """Format an ActiveProject into a dictionary compatible with ProjectOut schema."""
    rel_members = []
    if project.team_members:
        for pm in project.team_members:
            if pm.user:
                rel_members.append(
                    ProjectMemberOut(
                        user_id=pm.user.id,
                        full_name=pm.user.full_name,
                        email=pm.user.email,
                        role=pm.user.role,
                    )
                )
    return {
        "id": project.id,
        "name": project.name,
        "location": project.location,
        "sqft": project.sqft,
        "floors": project.floors,
        "structural_system": project.structural_system,
        "members": rel_members,
        "status": project.status,
    }


def get_all_active_projects(db: Session) -> List[Dict[str, Any]]:
    """Return all active construction projects from the database."""
    projects = (
        db.query(ActiveProject)
        .filter(ActiveProject.status == "ACTIVE")
        .order_by(ActiveProject.created_at.desc())
        .all()
    )
    return [format_project_out(p) for p in projects]


def get_assignable_users(db: Session) -> List[User]:
    """Return all active users eligible for project team assignment."""
    return (
        db.query(User)
        .filter(User.is_active == True)
        .order_by(User.full_name.asc())
        .all()
    )


def create_active_project(
    db: Session, payload: ProjectCreate, current_user: User
) -> Dict[str, Any]:
    """Create a new active construction project and persist it with team members in a single transaction."""
    # 1. Deduplicate member_ids safely
    raw_ids = payload.member_ids or []
    deduped_ids = list(dict.fromkeys(raw_ids))

    # 2. Validate member IDs exist and are active
    if deduped_ids:
        active_users = (
            db.query(User)
            .filter(User.id.in_(deduped_ids), User.is_active == True)
            .all()
        )
        if len(active_users) != len(deduped_ids):
            raise HTTPException(
                status_code=400,
                detail="One or more selected team members are invalid or inactive.",
            )

    try:
        # 3. Create ActiveProject
        project = ActiveProject(
            name=payload.name,
            location=payload.location,
            sqft=payload.sqft,
            floors=payload.floors,
            structural_system=payload.structural_system,
            status="ACTIVE",
            created_by=current_user.id,
        )
        db.add(project)
        db.flush()

        # 4. Create ProjectMember rows
        for uid in deduped_ids:
            pm = ProjectMember(
                project_id=project.id,
                user_id=uid,
                assigned_by=current_user.id,
            )
            db.add(pm)

        # 5. Create AuditLog
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
                "member_ids": deduped_ids,
            },
        )
        db.add(audit)

        # 6. Commit transaction
        db.commit()
        db.refresh(project)
        return format_project_out(project)
    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500, detail=f"Failed to create project: {str(e)}"
        )


def archive_active_project(
    db: Session, project_id: int, current_user: User
) -> Dict[str, Any]:
    """Soft-delete a project by setting status to ARCHIVED while preserving ProjectMember rows."""
    project = db.query(ActiveProject).filter(ActiveProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.status = "ARCHIVED"
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="PROJECT_ARCHIVED",
            details=f"Project '{project.name}' archived.",
            metadata_info={"project_id": project_id},
        )
    )
    db.commit()
    return format_project_out(project)

