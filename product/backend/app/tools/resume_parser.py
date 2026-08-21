"""Resume file parsing — extract raw text from PDF / DOCX / TXT.

Pipeline:
  PDF  → PyMuPDF (fitz) — fast, local, no external API
  DOCX → python-docx
  TXT  → direct read
"""

from __future__ import annotations

from pathlib import Path


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from a resume file.

    Args:
        file_bytes: Raw file contents.
        filename: Original filename (used to detect format).

    Returns:
        Extracted text string.

    Raises:
        ValueError: If the file format is unsupported.
    """
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(file_bytes)
    elif suffix in (".docx", ".doc"):
        return _extract_docx(file_bytes)
    elif suffix == ".txt":
        return file_bytes.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Use PDF, DOCX, or TXT.")


def _extract_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF using PyMuPDF (fitz)."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages: list[str] = []
    for page in doc:
        text = page.get_text("text")
        if text.strip():
            pages.append(text)
    doc.close()

    if not pages:
        raise ValueError("PDF appears to be empty or image-only (no extractable text).")

    return "\n\n".join(pages)


def _extract_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX using python-docx."""
    import io
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

    if not paragraphs:
        raise ValueError("DOCX appears to be empty.")

    return "\n".join(paragraphs)
