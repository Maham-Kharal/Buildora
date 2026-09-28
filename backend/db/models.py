import uuid
from sqlalchemy import Column, String, Float, Integer, Boolean, Text, Date, DateTime, ForeignKey, Numeric, JSON, UniqueConstraint
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

    project_memberships = relationship("ProjectMember", foreign_keys="[ProjectMember.user_id]", back_populates="user")

class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("active_projects.id"), nullable=True)
    image_url = Column(String(500), nullable=False)
    vendor_name = Column(String(255), nullable=True)
    total_amount = Column(Float, default=0.0)  # in $USD
    purchase_date = Column(Date, nullable=True)
    category = Column(String(100), nullable=True)
    status = Column(String(50), default="PENDING") # 'PENDING', 'APPROVED', 'REJECTED'
    flagged_anomaly = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("ReceiptItem", back_populates="receipt", cascade="all, delete-orphan")
    project = relationship("ActiveProject", foreign_keys=[project_id])


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
    project_key = Column(String(50), unique=True, index=True, nullable=False)
    project_title = Column(String(255), nullable=False)
    building_type = Column(String(100), nullable=True, index=True)
    location = Column(String(255), nullable=True, index=True)

    total_covered_area_sqft = Column(Float, nullable=True, index=True)
    building_footprint_sqft = Column(Float, nullable=True)

    basement_count = Column(Integer, nullable=True, index=True)
    above_ground_floors = Column(Integer, nullable=True, index=True)

    structural_system = Column(String(100), nullable=True, index=True)
    foundation_type = Column(String(100), nullable=True, index=True)
    floor_system = Column(String(100), nullable=True, index=True)

    total_rebar_net_lbs = Column(Float, nullable=True)
    total_rebar_with_wastage_lbs = Column(Float, nullable=True)
    overall_rebar_ratio_lbs_per_sqft = Column(Float, nullable=True)

    completion_year = Column(Integer, nullable=True)

    source_file = Column(String(255), nullable=True)
    source_pages = Column(String(100), nullable=True)

    data_quality = Column(String(50), default="VERIFIED", nullable=False, index=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    levels = relationship("HistoricalProjectLevel", back_populates="project", cascade="all, delete-orphan")
    steel_components = relationship("HistoricalSteelComponent", back_populates="project", cascade="all, delete-orphan")


class HistoricalProjectLevel(Base):
    __tablename__ = "historical_project_levels"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    level_key = Column(String(100), unique=True, index=True, nullable=False)
    project_id = Column(Integer, ForeignKey("historical_projects.id", ondelete="CASCADE"), nullable=False, index=True)

    level_type = Column(String(50), nullable=False, index=True)
    level_number = Column(Integer, nullable=True)
    level_label = Column(String(255), nullable=True)

    area_sqft = Column(Float, nullable=True)

    rebar_net_lbs = Column(Float, nullable=True)
    rebar_with_wastage_lbs = Column(Float, nullable=True)
    rebar_ratio_lbs_per_sqft = Column(Float, nullable=True)

    quantity_scope = Column(String(50), default="COMPLETE_LEVEL", nullable=False)

    source_file = Column(String(255), nullable=True)
    source_pages = Column(String(100), nullable=True)

    data_quality = Column(String(50), default="VERIFIED", nullable=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("HistoricalProject", back_populates="levels")
    components = relationship("HistoricalSteelComponent", back_populates="level")


class HistoricalSteelComponent(Base):
    __tablename__ = "historical_steel_components"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    component_key = Column(String(100), unique=True, index=True, nullable=False)
    project_id = Column(Integer, ForeignKey("historical_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    level_id = Column(Integer, ForeignKey("historical_project_levels.id", ondelete="SET NULL"), nullable=True, index=True)

    component_type = Column(String(100), nullable=False, index=True)
    component_label = Column(String(255), nullable=True)

    rebar_net_lbs = Column(Float, nullable=True)
    rebar_with_wastage_lbs = Column(Float, nullable=True)

    source_file = Column(String(255), nullable=True)
    source_pages = Column(String(100), nullable=True)

    data_quality = Column(String(50), default="VERIFIED", nullable=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("HistoricalProject", back_populates="steel_components")
    level = relationship("HistoricalProjectLevel", back_populates="components")
class ActiveProject(Base):
    __tablename__ = "active_projects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    sqft = Column(Float, nullable=False)
    floors = Column(Integer, nullable=False)
    structural_system = Column(String(100), nullable=False)
    status = Column(String(50), default="ACTIVE")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    team_members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_user_member"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("active_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("ActiveProject", back_populates="team_members")
    user = relationship("User", foreign_keys=[user_id], back_populates="project_memberships")
    assigner = relationship("User", foreign_keys=[assigned_by])


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
    content = Column(Text, nullable=True)  # Nullable for backwards compatibility with legacy seeded policies
    original_filename = Column(String(255), nullable=True)
    stored_filename = Column(String(255), nullable=True)
    file_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    index_status = Column(String(50), default="UPLOADED", nullable=True)
    chunk_count = Column(Integer, default=0, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(255), nullable=False)
    details = Column(Text, nullable=False)
    metadata_info = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())