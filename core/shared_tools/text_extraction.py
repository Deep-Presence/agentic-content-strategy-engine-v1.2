"""Shared text extraction from document files.

Supports .md, .txt, .pdf (via pdfplumber), and .docx (via python-docx).
Used by both the knowledge doc upload service and the s1 pipeline step.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text(file_path: Path) -> str:
    """Extract plain text from a file based on its extension.

    Returns empty string on failure or unsupported file type.
    """
    suffix = file_path.suffix.lower()

    if suffix in (".md", ".txt"):
        return file_path.read_text(encoding="utf-8", errors="replace")

    if suffix == ".pdf":
        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                return "\n\n".join(
                    page.extract_text() or "" for page in pdf.pages
                )
        except Exception as e:
            logger.warning("Failed to extract text from PDF %s: %s", file_path, e)
            return ""

    if suffix == ".docx":
        try:
            from docx import Document

            doc = Document(str(file_path))
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            logger.warning("Failed to extract text from DOCX %s: %s", file_path, e)
            return ""

    return ""
