from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.core.config import settings
from backend.core.database import engine, Base, SessionLocal, init_db
from backend.db.models import User, CompanyPolicy, ActiveProject, ProjectMember
from backend.db.historical_seed import seed_historical_data
from backend.core.security import get_password_hash

# Import Feature Routers
from backend.modules.auth.router import router as auth_router
from backend.modules.user.receipt_submission.router import router as user_receipt_router
from backend.modules.user.hr_assistant.router import router as user_assistant_router
from backend.modules.admin.receipt_monitoring.router import router as admin_receipt_router
from backend.modules.admin.expense_reports.router import router as admin_report_router
from backend.modules.admin.steel_estimator.router import router as admin_steel_router
from backend.modules.admin.audit_logs.router import router as admin_audit_router
from backend.modules.admin.projects.router import router as admin_projects_router
from backend.modules.admin.ai_chat.router import router as admin_ai_chat_router
from backend.modules.hr.user_management.router import router as hr_user_router
from backend.modules.hr.leave_management.router import router as hr_leave_router
from backend.modules.hr.policy_management.router import router as hr_policy_router

# Initialize FastAPI App
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Enable CORS for Frontend Client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Local Receipt Upload Images for $0 cost
uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(os.path.join(uploads_dir, "receipt_images"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Register Feature Routers under /api/v1
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(user_receipt_router, prefix=settings.API_V1_STR)
app.include_router(user_assistant_router, prefix=settings.API_V1_STR)
app.include_router(admin_receipt_router, prefix=settings.API_V1_STR)
app.include_router(admin_report_router, prefix=settings.API_V1_STR)
app.include_router(admin_steel_router, prefix=settings.API_V1_STR)
app.include_router(admin_audit_router, prefix=settings.API_V1_STR)
app.include_router(admin_projects_router, prefix=settings.API_V1_STR)
app.include_router(admin_ai_chat_router, prefix=settings.API_V1_STR)
app.include_router(hr_user_router, prefix=settings.API_V1_STR)
app.include_router(hr_leave_router, prefix=settings.API_V1_STR)
app.include_router(hr_policy_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
def startup_event():
    """Auto-create tables & seed default users on server startup for seamless testing."""
    init_db()

    db = SessionLocal()
    try:
        # Seed or Update Default Users
        user_passwords = {
            "worker@buildora.com": ("John Worker", "WORKER", "BuildoraPass123!"),
            "admin@buildora.com": ("Sarah Admin", "ADMIN", "BuildoraPass123!"),
            "maham@buildora.com": ("Maham Admin", "ADMIN", "Maham2004"),
            "hr@buildora.com": ("David HR", "HR_MANAGER", "BuildoraPass123!"),
        }
        for email, (full_name, role, pwd) in user_passwords.items():
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(email=email, full_name=full_name, role=role, password_hash=get_password_hash(pwd))
                db.add(user)
            else:
                user.password_hash = get_password_hash(pwd)
                user.is_active = True

        # Seed Company Policies if empty
        if db.query(CompanyPolicy).count() == 0:
            default_policies = [
                CompanyPolicy(title="Annual Paid Leave Entitlement", category="Leave & Benefits", content="Employees receive 15 days paid leave annually. Requests under 3 days are auto-approved."),
                CompanyPolicy(title="Field Site Safety Protocol", category="Safety & Site", content="Hard hats and high-visibility vests required at all construction sites at all times."),
                CompanyPolicy(title="Expense Reimbursement Limit", category="Expenses", content="All receipts above $100 USD require physical photo submission and approval.")
            ]
            db.add_all(default_policies)

        # Seed Historical Steel Dataset (22 Projects, 24 Levels, 54 Components)
        seed_historical_data(db)

        # Seed Active Projects if empty
        if db.query(ActiveProject).count() == 0:
            default_active_projects = [
                ActiveProject(
                    name="Austin Commercial Tower B",
                    location="Austin, TX",
                    sqft=45000,
                    floors=6,
                    structural_system="Reinforced Concrete Frame",
                    status="ACTIVE"
                ),
                ActiveProject(
                    name="Dallas Medical Center Annex",
                    location="Dallas, TX",
                    sqft=35000,
                    floors=4,
                    structural_system="Structural Steel Framing",
                    status="ACTIVE"
                ),
            ]
            db.add_all(default_active_projects)
            db.flush()

            worker = db.query(User).filter(User.email == "worker@buildora.com").first()
            admin = db.query(User).filter(User.email == "admin@buildora.com").first()
            if worker and admin:
                db.add_all([
                    ProjectMember(project_id=default_active_projects[0].id, user_id=worker.id),
                    ProjectMember(project_id=default_active_projects[0].id, user_id=admin.id),
                    ProjectMember(project_id=default_active_projects[1].id, user_id=worker.id),
                ])

        db.commit()
    except Exception as e:
        print(f"Startup DB Seed Warning: {e}")
    finally:
        db.close()

@app.get("/")
def root():
    return {
        "status": "online",
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)