"""AI-powered structured data extraction from classified documents."""

import logging

from ollama import Client
from pydantic import BaseModel, Field

from app.local_ai import LocalAIError, generate_structured

LOGGER = logging.getLogger(__name__)


class InvoiceData(BaseModel):
    """Invoice fields extracted from document text.

    Fields are optional during extraction because source documents may omit them.
    Strict validation and business rules are handled by later pipeline stages.
    """

    invoice_number: str | None
    company_name: str | None
    invoice_date: str | None
    due_date: str | None
    currency: str | None
    subtotal: float | None
    tax: float | None
    total: float | None
    email: str | None
    confidence: float = Field(ge=0, le=1)
    uncertain_fields: list[str]


class DataExtractionError(RuntimeError):
    """Raised when structured data cannot be extracted from a document."""


def extract_invoice_data(
    text: str,
    *,
    client: Client | None = None,
    model: str | None = None,
) -> InvoiceData:
    """Extract invoice fields using local Ollama Structured Outputs."""

    if not text.strip():
        raise DataExtractionError("Cannot extract data from an empty document")

    try:
        return generate_structured(
            text,
            instructions=(
                "Extract invoice data from the supplied document text. Return null "
                "for every field that is missing or uncertain. Do not infer or invent "
                "values. Preserve invoice numbers exactly. Use ISO 8601 YYYY-MM-DD "
                "for dates when the source provides an unambiguous date. Use a "
                "three-letter ISO currency code when identifiable. Return monetary "
                "values as numbers without currency symbols or thousands separators. "
                "Set confidence from 0 to 1 for the overall extraction and list every "
                "field whose value is uncertain. Return the result as JSON."
            ),
            schema=InvoiceData,
            client=client,
            model=model,
        )
    except LocalAIError as error:
        LOGGER.exception("Invoice data extraction failed")
        raise DataExtractionError(f"Invoice data extraction failed: {error}") from error
