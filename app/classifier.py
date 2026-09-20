"""AI-powered business document classification."""

import logging
import os
from enum import Enum

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

LOGGER = logging.getLogger(__name__)
DEFAULT_MODEL = "gpt-5.6-terra"


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
    client: OpenAI | None = None,
    model: str | None = None,
) -> DocumentClassification:
    """Classify extracted document text using OpenAI Structured Outputs."""

    if not text.strip():
        raise ClassificationError("Cannot classify an empty document")

    load_dotenv()
    selected_model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    if client is None:
        if not os.getenv("OPENAI_API_KEY"):
            raise ClassificationError(
                "OPENAI_API_KEY is not configured. Add it to the local .env file."
            )
        client = OpenAI()

    try:
        response = client.responses.parse(
            model=selected_model,
            instructions=(
                "Classify the business document into exactly one supported category. "
                "Use other only when it is not an invoice, purchase order, receipt, "
                "or contract. Base the decision only on the supplied document text."
            ),
            input=text,
            text_format=DocumentClassification,
        )
        result = response.output_parsed
        if result is None:
            raise ClassificationError("The model returned no classification")
        return result
    except ClassificationError:
        raise
    except Exception as error:
        LOGGER.exception("Document classification failed")
        raise ClassificationError(f"Document classification failed: {error}") from error
