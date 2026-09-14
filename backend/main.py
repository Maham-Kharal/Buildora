from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.core.config import settings
from backend.core.database import engine, Base

# Import Feature Routers
from backend.modules.auth.router import router as auth_router
from backend.modules.user.receipt_submission.router import router as user_receipt_router
from backend.modules.user.hr_assistant.router import router as user_assistant_router
from backend.modules.admin.receipt_monitoring.router import router as admin_receipt_router
from backend.modules.admin.expense_reports.router import router as admin_report_router
from backend.modules.admin.steel_estimator.router import router as admin_steel_router
from backend.modules.admin.audit_logs.router import router as admin_audit_router
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

# Register Feature Routers under /api
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(user_receipt_router, prefix=settings.API_V1_STR)
app.include_router(user_assistant_router, prefix=settings.API_V1_STR)
app.include_router(admin_receipt_router, prefix=settings.API_V1_STR)
app.include_router(admin_report_router, prefix=settings.API_V1_STR)
app.include_router(admin_steel_router, prefix=settings.API_V1_STR)
app.include_router(admin_audit_router, prefix=settings.API_V1_STR)
app.include_router(hr_user_router, prefix=settings.API_V1_STR)
app.include_router(hr_leave_router, prefix=settings.API_V1_STR)
app.include_router(hr_policy_router, prefix=settings.API_V1_STR)

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