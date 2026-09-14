import uuid
from sqlalchemy import Column, String, Float, Integer, Boolean, Text, Date, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    role = Column(String(50), nullable=False)  # 'ADMIN', 'HR_MANAGER', 'NORMAL_USER'
    manager_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    active_status = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_name = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)  # e.g., "Austin, TX"
    covered_area = Column(Numeric(10, 2), nullable=False)  # sq ft
    number_of_floors = Column(Integer, nullable=False)
    structural_system = Column(String(100), nullable=False)
    floor_system = Column(String(100), nullable=False)
    foundation_type = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ProjectUser(Base):
    __tablename__ = "project_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())

class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    image_path = Column(String(500), nullable=False)
    vendor_name = Column(String(255), nullable=True)
    receipt_number = Column(String(100), nullable=True)
    receipt_date = Column(Date, nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=True)  # in $USD
    category = Column(String(100), nullable=True)
    custom_description = Column(Text, nullable=True)
    status = Column(String(50), default="Submitted")
    ocr_confidence = Column(Numeric(5, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("ReceiptItem", back_populates="receipt", cascade="all, delete-orphan")

class ReceiptItem(Base):
    __tablename__ = "receipt_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    receipt_id = Column(UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False)
    material_name = Column(String(255), nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False)
    unit = Column(String(50), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)  # in $USD
    total_price = Column(Numeric(12, 2), nullable=False)  # in $USD

    receipt = relationship("Receipt", back_populates="items")

class PriceComparison(Base):
    __tablename__ = "price_comparisons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    receipt_item_id = Column(UUID(as_uuid=True), ForeignKey("receipt_items.id", ondelete="CASCADE"), nullable=False)
    purchased_price = Column(Numeric(10, 2), nullable=False)
    market_price = Column(Numeric(10, 2), nullable=False)
    difference_percentage = Column(Numeric(5, 2), nullable=False)
    threshold_percentage = Column(Numeric(5, 2), default=15.00)
    status = Column(String(50), default="Normal")  # 'Normal' or 'Requires Admin Review'
    source_url = Column(Text, nullable=True)
    searched_at = Column(DateTime(timezone=True), server_default=func.now())

class HistoricalProject(Base):
    __tablename__ = "historical_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_title = Column(String(255), nullable=False)
    building_type = Column(String(100), nullable=False)
    us_location = Column(String(100), nullable=False)
    covered_area_sqft = Column(Numeric(10, 2), nullable=False)
    floors = Column(Integer, nullable=False)
    structural_system = Column(String(100), nullable=False)
    floor_system = Column(String(100), nullable=False)
    foundation_type = Column(String(100), nullable=False)
    total_steel_lbs = Column(Numeric(12, 2), nullable=False)
    steel_ratio_lbs_per_sqft = Column(Numeric(8, 3), nullable=False)

class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    total_annual_leaves = Column(Integer, default=24)
    used_leaves_annual = Column(Integer, default=0)
    remaining_annual_leaves = Column(Integer, default=24)
    monthly_allowance = Column(Integer, default=3)
    used_leaves_this_month = Column(Integer, default=0)

class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    manager_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    leave_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(50), nullable=False)  # 'Approved' or 'Pending Manager Approval'
    auto_approved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CompanyPolicy(Base):
    __tablename__ = "company_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(255), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    metadata_info = Column(JSONB, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())