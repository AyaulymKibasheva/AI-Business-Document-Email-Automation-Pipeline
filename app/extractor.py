"""Plain-text extraction from supported business documents."""

import logging
from pathlib import Path

from app.observability import configure_logging
from app.parser import DocumentType, UploadedDocument

LOGGER = logging.getLogger(__name__)


class TextExtractionError(RuntimeError):
    """Raised when readable text cannot be extracted from a document."""


def _extract_pdf(path: Path) -> str:
    import pymupdf

    with pymupdf.open(path) as document:
        return "\n".join(page.get_text() for page in document)


def _extract_docx(path: Path) -> str:
    from docx import Document

    document = Document(path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def extract_text(document: UploadedDocument) -> str:
    """Extract and return normalized plain text from a document."""

    configure_logging()
    extractors = {
        DocumentType.PDF: _extract_pdf,
        DocumentType.DOCX: _extract_docx,
        DocumentType.TXT: _extract_txt,
    }

    try:
        text = extractors[document.document_type](document.path).strip()
        if not text:
            raise TextExtractionError("No readable text found in the document")
        return text
    except TextExtractionError:
        LOGGER.exception("Text extraction failed for %s", document.path)
        raise
    except Exception as error:
        LOGGER.exception("Text extraction failed for %s", document.path)
        raise TextExtractionError(
            f"Could not extract text from '{document.filename}': {error}"
        ) from error
