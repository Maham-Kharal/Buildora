import os
import logging
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from fastapi import HTTPException, UploadFile
from backend.core.config import settings
from backend.core.database import engine
from backend.db.models import CompanyPolicy, AuditLog
from backend.shared.storage import save_uploaded_policy_file, delete_stored_policy_file
from backend.shared.ai.gemini import generate_embeddings
from backend.shared.ai.qdrant import (
    upsert_policy_chunks,
    delete_policy_chunks_by_document_id,
    generate_deterministic_point_id
)
from backend.modules.hr.policy_management.document_processor import (
    process_and_chunk_document,
    OcrRequiredException
)

logger = logging.getLogger("buildora.policy_service")

def migrate_company_policies_table():
    """
    Ensures SQLite company_policies table is automatically updated with document metadata columns
    without dropping the database or losing existing seeded records.
    """
    try:
        inspector = inspect(engine)
        if "company_policies" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("company_policies")]
            with engine.begin() as conn:
                if "original_filename" not in columns:
                    conn.execute(text("ALTER TABLE company_policies ADD COLUMN original_filename VARCHAR(255)"))
                if "stored_filename" not in columns:
                    conn.execute(text("ALTER TABLE company_policies ADD COLUMN stored_filename VARCHAR(255)"))
                if "file_type" not in columns:
                    conn.execute(text("ALTER TABLE company_policies ADD COLUMN file_type VARCHAR(100)"))
                if "file_size" not in columns:
                    conn.execute(text("ALTER TABLE company_policies ADD COLUMN file_size INTEGER"))
                if "uploaded_by" not in columns:
                    conn.execute(text("ALTER TABLE company_policies ADD COLUMN uploaded_by INTEGER REFERENCES users(id)"))
                if "index_status" not in columns:
                    conn.execute(text("ALTER TABLE company_policies ADD COLUMN index_status VARCHAR(50) DEFAULT 'UPLOADED'"))
                if "chunk_count" not in columns:
                    conn.execute(text("ALTER TABLE company_policies ADD COLUMN chunk_count INTEGER DEFAULT 0"))
                if "updated_at" not in columns:
                    conn.execute(text("ALTER TABLE company_policies ADD COLUMN updated_at DATETIME"))
    except Exception as e:
        # Ignore errors if table doesn't exist yet or columns already added
        pass

# Run table migration on module load
migrate_company_policies_table()

def index_policy_document(db: Session, policy: CompanyPolicy) -> CompanyPolicy:
    """
    Synchronous document indexing pipeline with Zero-Downtime Safe Reindexing:
    1. Extract text and split document into chunks.
    2. Generate embeddings using Gemini SDK (gemini-embedding-2, 768 dimensions).
    3. Prepare new points with deterministic IDs.
    4. Upsert new points into Qdrant FIRST (overwriting overlapping indices).
    5. Clean up stale points if the new document has fewer chunks than before.
    6. Update SQLite metadata status to 'INDEXED' and chunk_count to N.
    """
    previous_chunk_count = policy.chunk_count or 0
    previous_status = policy.index_status or "UPLOADED"

    policy.index_status = "INDEXING"
    db.commit()
    db.refresh(policy)

    file_path = os.path.join(settings.POLICY_UPLOAD_DIR, policy.stored_filename)

    try:
        # Step A: Text Extraction & Chunking
        chunks = process_and_chunk_document(
            file_path=file_path,
            file_type=policy.file_type or "TXT",
            policy_document_id=policy.id,
            title=policy.title,
            category=policy.category,
            original_filename=policy.original_filename or "document"
        )

        if not chunks:
            policy.index_status = "FAILED"
            if previous_status != "INDEXED":
                policy.chunk_count = 0
            db.commit()
            return policy

        # Step B: Generate Embeddings
        chunk_texts = [c["text"] for c in chunks]
        embeddings = generate_embeddings(chunk_texts)

        # Step C: Prepare Qdrant Points with Deterministic IDs
        qdrant_points = []
        for idx, (chunk_data, vector) in enumerate(zip(chunks, embeddings)):
            point_id = generate_deterministic_point_id(policy.id, idx)
            qdrant_points.append({
                "id": point_id,
                "vector": vector,
                "payload": chunk_data
            })

        # Step D: Safe Reindexing — Upsert new points FIRST before deleting stale points
        upsert_policy_chunks(qdrant_points)

        # Step E: Clean up stale points if document shrank (fewer chunks than previous index)
        if previous_chunk_count > len(chunks):
            stale_ids = [
                generate_deterministic_point_id(policy.id, idx)
                for idx in range(len(chunks), previous_chunk_count)
            ]
            from backend.shared.ai.qdrant import delete_specific_qdrant_point_ids
            delete_specific_qdrant_point_ids(stale_ids)

        # Step F: Update Metadata Row
        policy.index_status = "INDEXED"
        policy.chunk_count = len(chunks)
        db.commit()
        db.refresh(policy)
        logger.info(f"Successfully indexed policy_document_id={policy.id} ({len(chunks)} chunks).")
        return policy

    except OcrRequiredException as e:
        logger.warning(f"Policy document ID #{policy.id} requires OCR: {e}")
        policy.index_status = "OCR_REQUIRED"
        if previous_status != "INDEXED":
            policy.chunk_count = 0
        db.commit()
        db.refresh(policy)
        return policy
    except Exception as e:
        logger.error(f"Indexing failed for policy_document_id={policy.id}: {e}", exc_info=True)
        policy.index_status = "FAILED"
        if previous_status != "INDEXED":
            policy.chunk_count = 0
        db.commit()
        db.refresh(policy)
        return policy

def upload_policy_document(db: Session, hr_id: int, title: str, category: str, file: UploadFile):
    migrate_company_policies_table()
    file_meta = save_uploaded_policy_file(file)

    policy = CompanyPolicy(
        title=title,
        category=category,
        content="",  # Empty string satisfies legacy SQLite NOT NULL constraint
        original_filename=file_meta["original_filename"],
        stored_filename=file_meta["stored_filename"],
        file_type=file_meta["file_type"],
        file_size=file_meta["file_size"],
        uploaded_by=hr_id,
        index_status="UPLOADED",
        chunk_count=0
    )
    db.add(policy)
    
    audit = AuditLog(
        user_id=hr_id,
        action="UPLOAD_POLICY_DOCUMENT",
        details=f"HR uploaded policy document '{file_meta['original_filename']}' for policy '{title}'."
    )
    db.add(audit)
    db.commit()
    db.refresh(policy)

    # Automatically trigger indexing pipeline
    return index_policy_document(db, policy)

def list_policy_documents(db: Session):
    migrate_company_policies_table()
    return db.query(CompanyPolicy).order_by(CompanyPolicy.created_at.desc()).all()

def delete_policy_document(db: Session, hr_id: int, policy_id: int):
    migrate_company_policies_table()
    policy = db.query(CompanyPolicy).filter(CompanyPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy document not found")
    
    # 1. Delete Qdrant vector points associated with policy_document_id
    delete_policy_chunks_by_document_id(policy.id)

    # 2. Delete stored file from disk
    if policy.stored_filename:
        delete_stored_policy_file(policy.stored_filename)

    # 3. Delete metadata row from SQLite DB
    db.delete(policy)
    audit = AuditLog(
        user_id=hr_id,
        action="DELETE_POLICY_DOCUMENT",
        details=f"HR deleted policy document ID #{policy_id} ('{policy.title}')."
    )
    db.add(audit)
    db.commit()
    return {"message": "Policy document deleted successfully"}

