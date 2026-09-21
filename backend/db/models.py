import uuid
from sqlalchemy import Column, String, Float, Integer, Boolean, Text, Date, DateTime, ForeignKey, Numeric, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # 'ADMIN', 'HR_MANAGER', 'WORKER'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    image_url = Column(String(500), nullable=False)
    vendor_name = Column(String(255), nullable=True)
    total_amount = Column(Float, default=0.0)  # in $USD
    purchase_date = Column(Date, nullable=True)
    category = Column(String(100), nullable=True)
    status = Column(String(50), default="PENDING") # 'PENDING', 'APPROVED', 'REJECTED'
    flagged_anomaly = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("ReceiptItem", back_populates="receipt", cascade="all, delete-orphan")

class ReceiptItem(Base):
    __tablename__ = "receipt_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False)
    item_name = Column(String(255), nullable=False)
    quantity = Column(Float, default=1.0)
    unit_price = Column(Float, default=0.0)  # in $USD
    total_price = Column(Float, default=0.0)  # in $USD

    receipt = relationship("Receipt", back_populates="items")

class HistoricalProject(Base):
    __tablename__ = "historical_projects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    project_type = Column(String(100), nullable=False)
    sqft = Column(Float, nullable=False)
    steel_tons_used = Column(Float, nullable=False)
    cost_usd = Column(Float, nullable=False)
    location = Column(String(200), nullable=False)

class ActiveProject(Base):
    __tablename__ = "active_projects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    sqft = Column(Float, nullable=False)
    floors = Column(Integer, nullable=False)
    structural_system = Column(String(100), nullable=False)
    members = Column(JSON, nullable=True, default=list)  # list of member name strings
    status = Column(String(50), default="ACTIVE")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    days = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(50), default="PENDING")  # 'APPROVED', 'PENDING', 'REJECTED'
    auto_approved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CompanyPolicy(Base):
    __tablename__ = "company_policies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    category = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(255), nullable=False)
    details = Column(Text, nullable=False)
    metadata_info = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())