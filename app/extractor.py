"""Plain-text extraction from supported business documents."""

import logging
from pathlib import Path

from app.parser import DocumentType, UploadedDocument

LOGGER = logging.getLogger(__name__)


class TextExtractionError(RuntimeError):
    """Raised when readable text cannot be extracted from a document."""


def configure_logging(log_path: str | Path = "logs/app.log") -> None:
    """Configure the application file log once."""

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    resolved_path = path.resolve()
    if any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == resolved_path
        for handler in LOGGER.handlers
    ):
        return

    handler = logging.FileHandler(resolved_path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)


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
