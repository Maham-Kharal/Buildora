import os
import re
from typing import List, Dict, Any, Tuple, Optional
import pypdf
import docx
from backend.core.config import settings

class OcrRequiredException(Exception):
    """Raised when a PDF contains no extractable text (scanned image-only PDF)."""
    pass

def split_text_into_chunks(
    text: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None
) -> List[str]:
    """
    Deterministic chunking helper that splits a block of text into overlapping semantic segments.
    Uses configurable chunk size and overlap settings.
    """
    size = chunk_size or settings.POLICY_CHUNK_SIZE
    overlap = chunk_overlap or settings.POLICY_CHUNK_OVERLAP

    cleaned_text = re.sub(r'\s+', ' ', text).strip()
    if not cleaned_text:
        return []

    if len(cleaned_text) <= size:
        return [cleaned_text]

    chunks: List[str] = []
    start = 0
    while start < len(cleaned_text):
        end = start + size
        chunk = cleaned_text[start:end]

        # Avoid breaking words in middle if possible
        if end < len(cleaned_text):
            last_space = chunk.rfind(' ')
            if last_space > size // 2:
                end = start + last_space
                chunk = cleaned_text[start:end]

        chunk_str = chunk.strip()
        if chunk_str:
            chunks.append(chunk_str)

        start = end - overlap if (end - overlap) > start else end

    return chunks

def extract_and_chunk_pdf(
    file_path: str,
    policy_document_id: int,
    title: str,
    category: str,
    original_filename: str
) -> List[Dict[str, Any]]:
    """
    Extracts text page-by-page from a PDF file using pypdf.
    Preserves page numbers in metadata payload.
    Raises OcrRequiredException if PDF has no extractable text.
    """
    try:
        reader = pypdf.PdfReader(file_path)
        total_extracted_text = ""
        page_texts: List[Tuple[int, str]] = []

        for i, page in enumerate(reader.pages):
            page_num = i + 1
            text = page.extract_text() or ""
            total_extracted_text += text
            if text.strip():
                page_texts.append((page_num, text))

        # Check if PDF contains extractable text
        if not re.search(r'[a-zA-Z0-9]', total_extracted_text):
            raise OcrRequiredException("PDF document contains no extractable text (scanned image-only PDF). OCR required.")
    except OcrRequiredException:
        raise
    except Exception as e:
        raise OcrRequiredException(f"PDF text extraction failed or requires OCR: {e}")

    all_chunks: List[Dict[str, Any]] = []
    chunk_counter = 0

    for page_num, text in page_texts:
        page_chunks = split_text_into_chunks(text)
        for chunk_text in page_chunks:
            all_chunks.append({
                "policy_document_id": policy_document_id,
                "title": title,
                "category": category,
                "original_filename": original_filename,
                "page_number": page_num,
                "chunk_index": chunk_counter,
                "text": chunk_text
            })
            chunk_counter += 1

    return all_chunks

def extract_and_chunk_docx(
    file_path: str,
    policy_document_id: int,
    title: str,
    category: str,
    original_filename: str
) -> List[Dict[str, Any]]:
    """
    Extracts text from a DOCX file using python-docx.
    Sets page_number = None (DOCX documents do not naturally contain page boundaries).
    """
    doc = docx.Document(file_path)
    full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

    if not re.search(r'[a-zA-Z0-9]', full_text):
        raise ValueError("DOCX document contains no text.")

    text_chunks = split_text_into_chunks(full_text)
    all_chunks: List[Dict[str, Any]] = []

    for idx, chunk_text in enumerate(text_chunks):
        all_chunks.append({
            "policy_document_id": policy_document_id,
            "title": title,
            "category": category,
            "original_filename": original_filename,
            "page_number": None,
            "chunk_index": idx,
            "text": chunk_text
        })

    return all_chunks

def extract_and_chunk_txt(
    file_path: str,
    policy_document_id: int,
    title: str,
    category: str,
    original_filename: str
) -> List[Dict[str, Any]]:
    """
    Extracts plain text from a TXT file.
    Sets page_number = None.
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        full_text = f.read()

    if not re.search(r'[a-zA-Z0-9]', full_text):
        raise ValueError("TXT file contains no text.")

    text_chunks = split_text_into_chunks(full_text)
    all_chunks: List[Dict[str, Any]] = []

    for idx, chunk_text in enumerate(text_chunks):
        all_chunks.append({
            "policy_document_id": policy_document_id,
            "title": title,
            "category": category,
            "original_filename": original_filename,
            "page_number": None,
            "chunk_index": idx,
            "text": chunk_text
        })

    return all_chunks

def process_and_chunk_document(
    file_path: str,
    file_type: str,
    policy_document_id: int,
    title: str,
    category: str,
    original_filename: str
) -> List[Dict[str, Any]]:
    """
    Unified entrypoint to extract and chunk a document based on its file extension type (PDF, DOCX, TXT).
    """
    ext = file_type.upper().lstrip('.')
    if ext == "PDF":
        return extract_and_chunk_pdf(file_path, policy_document_id, title, category, original_filename)
    elif ext in ("DOCX", "DOC"):
        return extract_and_chunk_docx(file_path, policy_document_id, title, category, original_filename)
    elif ext == "TXT":
        return extract_and_chunk_txt(file_path, policy_document_id, title, category, original_filename)
    else:
        raise ValueError(f"Unsupported file format '{ext}' for text extraction.")
