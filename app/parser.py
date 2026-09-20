"""Document intake and type detection."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class DocumentType(str, Enum):
    """File types accepted by the document pipeline."""

    PDF = "PDF"
    DOCX = "DOCX"
    TXT = "TXT"


SUPPORTED_EXTENSIONS = {
    ".pdf": DocumentType.PDF,
    ".docx": DocumentType.DOCX,
    ".txt": DocumentType.TXT,
}


class UnsupportedDocumentError(ValueError):
    """Raised when a document has an unsupported file extension."""


@dataclass(frozen=True)
class UploadedDocument:
    """A validated document ready to enter the processing pipeline."""

    path: Path
    document_type: DocumentType

    @property
    def filename(self) -> str:
        return self.path.name


def receive_document(file_path: str | Path) -> UploadedDocument:
    """Validate a local upload and detect its supported document type."""

    path = Path(file_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")
    if not path.is_file():
        raise ValueError(f"Document path is not a file: {path}")

    document_type = SUPPORTED_EXTENSIONS.get(path.suffix.lower())
    if document_type is None:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise UnsupportedDocumentError(
            f"Unsupported document type '{path.suffix or '<none>'}'. "
            f"Supported extensions: {supported}"
        )

    return UploadedDocument(path=path.resolve(), document_type=document_type)
