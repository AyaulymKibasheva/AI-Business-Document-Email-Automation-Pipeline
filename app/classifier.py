"""AI-powered business document classification."""

import logging
from enum import Enum

from ollama import Client
from pydantic import BaseModel

from app.local_ai import LocalAIError, generate_structured

LOGGER = logging.getLogger(__name__)


class DocumentCategory(str, Enum):
    """Business document categories supported by the pipeline."""

    INVOICE = "invoice"
    PURCHASE_ORDER = "purchase_order"
    RECEIPT = "receipt"
    CONTRACT = "contract"
    OTHER = "other"


class DocumentClassification(BaseModel):
    """Strict structured result returned by the AI classifier."""

    document_type: DocumentCategory


class ClassificationError(RuntimeError):
    """Raised when a document cannot be classified."""


def classify_document(
    text: str,
    *,
    client: Client | None = None,
    model: str | None = None,
) -> DocumentClassification:
    """Classify extracted document text using local Ollama Structured Outputs."""

    if not text.strip():
        raise ClassificationError("Cannot classify an empty document")

    try:
        return generate_structured(
            text,
            instructions=(
                "Classify the business document into exactly one supported category. "
                "Use other only when it is not an invoice, purchase order, receipt, "
                "or contract. Base the decision only on the supplied document text. "
                "Return the result as JSON."
            ),
            schema=DocumentClassification,
            client=client,
            model=model,
        )
    except LocalAIError as error:
        LOGGER.exception("Document classification failed")
        raise ClassificationError(f"Document classification failed: {error}") from error
