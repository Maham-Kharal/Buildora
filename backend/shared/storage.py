import os
import uuid
from fastapi import UploadFile, HTTPException
from backend.core.config import settings

ALLOWED_POLICY_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_POLICY_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

def save_uploaded_file(file: UploadFile) -> str:
    """
    Saves an uploaded image file to disk in backend/uploads/receipt_images/.
    Returns relative web path (e.g. '/uploads/receipt_images/<uuid>_<filename>').
    Preserved untouched to ensure receipt uploads work exactly as before.
    """
    ext = os.path.splitext(file.filename or "")[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)

    with open(filepath, "wb") as buffer:
        buffer.write(file.file.read())

    return f"/uploads/receipt_images/{filename}"

def save_uploaded_policy_file(file: UploadFile) -> dict:
    """
    Validates and saves an uploaded HR policy document (.pdf, .docx, .txt) to backend/uploads/policy_documents/.
    Returns dictionary with storage metadata:
    - original_filename
    - stored_filename
    - file_type
    - file_size
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing from upload")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_POLICY_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type '{ext}'. Allowed extensions are: .pdf, .docx, .txt"
        )

    content = file.file.read()
    file_size = len(content)
    if file_size > MAX_POLICY_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File size exceeds maximum allowed limit of 10MB"
        )
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    stored_filename = f"{uuid.uuid4().hex}{ext}"
    target_path = os.path.join(settings.POLICY_UPLOAD_DIR, stored_filename)

    with open(target_path, "wb") as f:
        f.write(content)

    return {
        "original_filename": file.filename,
        "stored_filename": stored_filename,
        "file_type": ext.lstrip('.').upper(),
        "file_size": file_size
    }

def delete_stored_policy_file(stored_filename: str) -> bool:
    """
    Safely deletes a policy file from disk if it exists.
    Handles missing files gracefully without throwing errors.
    """
    if not stored_filename:
        return False
    target_path = os.path.join(settings.POLICY_UPLOAD_DIR, stored_filename)
    if os.path.exists(target_path):
        try:
            os.remove(target_path)
            return True
        except Exception:
            return False
    return False
