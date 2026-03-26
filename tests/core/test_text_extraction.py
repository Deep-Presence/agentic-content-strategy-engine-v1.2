"""Tests for extract_text_from_bytes() — in-memory text extraction without filesystem.

Phase 6 of R2 blob storage migration: enables knowledge doc text extraction
from StorageBackend bytes instead of requiring a local Path.
"""
from __future__ import annotations

import pytest


class TestExtractTextFromBytes:
    """extract_text_from_bytes() should extract text from in-memory bytes."""

    def test_markdown_bytes(self) -> None:
        from core.shared_tools.text_extraction import extract_text_from_bytes

        content = b"# Title\n\nSome markdown content here."
        result = extract_text_from_bytes(content, ".md")
        assert "Title" in result
        assert "markdown content" in result

    def test_txt_bytes(self) -> None:
        from core.shared_tools.text_extraction import extract_text_from_bytes

        content = b"Plain text document content."
        result = extract_text_from_bytes(content, ".txt")
        assert result == "Plain text document content."

    def test_txt_uppercase_suffix(self) -> None:
        from core.shared_tools.text_extraction import extract_text_from_bytes

        content = b"Uppercase suffix test."
        result = extract_text_from_bytes(content, ".TXT")
        assert result == "Uppercase suffix test."

    def test_unsupported_extension_returns_empty(self) -> None:
        from core.shared_tools.text_extraction import extract_text_from_bytes

        result = extract_text_from_bytes(b"binary data", ".exe")
        assert result == ""

    def test_empty_bytes_returns_empty(self) -> None:
        from core.shared_tools.text_extraction import extract_text_from_bytes

        result = extract_text_from_bytes(b"", ".md")
        assert result == ""

    def test_utf8_with_special_chars(self) -> None:
        from core.shared_tools.text_extraction import extract_text_from_bytes

        content = "Unicode: \u00e9\u00e0\u00fc \u2014 em dash".encode("utf-8")
        result = extract_text_from_bytes(content, ".txt")
        assert "\u00e9\u00e0\u00fc" in result
        assert "\u2014" in result

    def test_invalid_utf8_replaced(self) -> None:
        from core.shared_tools.text_extraction import extract_text_from_bytes

        content = b"Valid start \xff\xfe invalid bytes"
        result = extract_text_from_bytes(content, ".md")
        assert "Valid start" in result
        # Invalid bytes should be replaced, not raise
        assert "\ufffd" in result

    def test_pdf_bytes_with_mock(self) -> None:
        """PDF extraction via pdfplumber from BytesIO."""
        from unittest.mock import MagicMock, patch

        from core.shared_tools.text_extraction import extract_text_from_bytes

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "PDF page content"
        mock_pdf = MagicMock()
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        mock_pdf.pages = [mock_page]

        with patch("pdfplumber.open", return_value=mock_pdf) as mock_open:
            result = extract_text_from_bytes(b"fake pdf bytes", ".pdf")
            assert result == "PDF page content"
            # Verify BytesIO was passed (not a Path)
            call_arg = mock_open.call_args[0][0]
            import io
            assert isinstance(call_arg, io.BytesIO)

    def test_docx_bytes_with_mock(self) -> None:
        """DOCX extraction via python-docx from BytesIO."""
        from unittest.mock import MagicMock, patch

        from core.shared_tools.text_extraction import extract_text_from_bytes

        mock_para1 = MagicMock()
        mock_para1.text = "First paragraph"
        mock_para2 = MagicMock()
        mock_para2.text = "Second paragraph"
        mock_para_empty = MagicMock()
        mock_para_empty.text = "   "  # whitespace-only, should be skipped
        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para1, mock_para_empty, mock_para2]

        with patch("docx.Document", return_value=mock_doc) as mock_ctor:
            result = extract_text_from_bytes(b"fake docx bytes", ".docx")
            assert "First paragraph" in result
            assert "Second paragraph" in result
            # Verify BytesIO was passed
            call_arg = mock_ctor.call_args[0][0]
            import io
            assert isinstance(call_arg, io.BytesIO)
