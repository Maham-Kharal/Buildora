import os
import shutil
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from backend.core.config import settings

# If deploying SQLite to a persistent volume (e.g., sqlite:////data/buildora.db),
# bootstrap from repository seed buildora.db on first boot if target file does not exist yet.
if settings.DATABASE_URL.startswith("sqlite"):
    db_file_path = settings.DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
    if db_file_path and not db_file_path.startswith(":memory:"):
        abs_db_path = os.path.abspath(db_file_path)
        if not os.path.exists(abs_db_path):
            repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            seed_db = os.path.join(repo_root, "buildora.db")
            if os.path.exists(seed_db):
                os.makedirs(os.path.dirname(abs_db_path), exist_ok=True)
                shutil.copyfile(seed_db, abs_db_path)

# Handle SQLite vs PostgreSQL engine options
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True if not settings.DATABASE_URL.startswith("sqlite") else False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables and run safe column/schema migrations for SQLite."""
    from sqlalchemy import text
    if settings.DATABASE_URL.startswith("sqlite"):
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))

            # Staged migration: check for obsolete single-table historical_projects schema
            hp_info = conn.execute(text("PRAGMA table_info(historical_projects)")).fetchall()
            hp_columns = [row[1] for row in hp_info]
            if hp_info and ("steel_tons_used" in hp_columns or "project_key" not in hp_columns):
                # Rename old historical table temporarily
                conn.execute(text("ALTER TABLE historical_projects RENAME TO _old_historical_projects_backup"))
                conn.commit()

            # 1. Add project_id to receipts if not present
            result = conn.execute(text("PRAGMA table_info(receipts)")).fetchall()
            columns = [row[1] for row in result]
            if result and "project_id" not in columns:
                conn.execute(text("ALTER TABLE receipts ADD COLUMN project_id INTEGER REFERENCES active_projects(id)"))
                conn.commit()

            # 2. Safely drop obsolete active_projects.members column if present
            ap_info = conn.execute(text("PRAGMA table_info(active_projects)")).fetchall()
            ap_columns = [row[1] for row in ap_info]
            if ap_info and "members" in ap_columns:
                conn.execute(text("ALTER TABLE active_projects DROP COLUMN members"))
                conn.commit()

    Base.metadata.create_all(bind=engine)