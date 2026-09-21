from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.core.config import settings
from backend.core.database import engine, Base, SessionLocal
from backend.db.models import User, CompanyPolicy, HistoricalProject, ActiveProject
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
app.include_router(hr_user_router, prefix=settings.API_V1_STR)
app.include_router(hr_leave_router, prefix=settings.API_V1_STR)
app.include_router(hr_policy_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
def startup_event():
    """Auto-create tables & seed default users on server startup for seamless testing."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Seed Users if table is empty
        if db.query(User).count() == 0:
            default_users = [
                User(email="worker@buildora.com", full_name="John Worker", role="WORKER", password_hash=get_password_hash("password123")),
                User(email="admin@buildora.com", full_name="Sarah Admin", role="ADMIN", password_hash=get_password_hash("admin123")),
                User(email="hr@buildora.com", full_name="David HR", role="HR_MANAGER", password_hash=get_password_hash("hr123")),
            ]
            db.add_all(default_users)

        # Seed Company Policies if empty
        if db.query(CompanyPolicy).count() == 0:
            default_policies = [
                CompanyPolicy(title="Annual Paid Leave Entitlement", category="Leave & Benefits", content="Employees receive 15 days paid leave annually. Requests under 3 days are auto-approved."),
                CompanyPolicy(title="Field Site Safety Protocol", category="Safety & Site", content="Hard hats and high-visibility vests required at all construction sites at all times."),
                CompanyPolicy(title="Expense Reimbursement Limit", category="Expenses", content="All receipts above $100 USD require physical photo submission and approval.")
            ]
            db.add_all(default_policies)

        # Seed Historical Projects if empty (25 projects)
        if db.query(HistoricalProject).count() == 0:
            past_projects = [
                HistoricalProject(name="Austin High-Rise Tower A", project_type="Commercial", sqft=50000, steel_tons_used=112.5, cost_usd=110250, location="Austin, TX"),
                HistoricalProject(name="Dallas Medical Center Annex", project_type="Commercial", sqft=35000, steel_tons_used=78.75, cost_usd=77175, location="Dallas, TX"),
                HistoricalProject(name="Houston Industrial Hub #3", project_type="Industrial", sqft=80000, steel_tons_used=272.0, cost_usd=266560, location="Houston, TX"),
                HistoricalProject(name="San Antonio Highway Flyover", project_type="Bridge / Civil", sqft=60000, steel_tons_used=204.0, cost_usd=199920, location="San Antonio, TX"),
                HistoricalProject(name="Fort Worth Residential Complex", project_type="Residential", sqft=42000, steel_tons_used=94.5, cost_usd=92610, location="Fort Worth, TX"),
            ]
            # Add up to 25 project entries
            for i in range(6, 26):
                sqft_val = 20000 + (i * 2500)
                tons_val = round((sqft_val * 4.5) / 2000.0, 2)
                past_projects.append(HistoricalProject(
                    name=f"US Civil Structural Takeoff #{i}",
                    project_type="Commercial" if i % 2 == 0 else "Residential",
                    sqft=sqft_val,
                    steel_tons_used=tons_val,
                    cost_usd=round(tons_val * 980.0, 2),
                    location="Texas, US"
                ))
            db.add_all(past_projects)

        # Seed Active Projects if empty
        if db.query(ActiveProject).count() == 0:
            default_active_projects = [
                ActiveProject(
                    name="Austin Commercial Tower B",
                    location="Austin, TX",
                    sqft=45000,
                    floors=6,
                    structural_system="Reinforced Concrete Frame",
                    members=["John Worker (Worker)", "Sarah Admin (Admin)"],
                    status="ACTIVE"
                ),
                ActiveProject(
                    name="Dallas Medical Center Annex",
                    location="Dallas, TX",
                    sqft=35000,
                    floors=4,
                    structural_system="Structural Steel Framing",
                    members=["John Worker (Worker)"],
                    status="ACTIVE"
                ),
            ]
            db.add_all(default_active_projects)

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