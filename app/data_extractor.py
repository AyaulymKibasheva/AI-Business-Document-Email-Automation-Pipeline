"""AI-powered structured data extraction from classified documents."""

import logging
import os

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

from app.classifier import DEFAULT_MODEL

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


class DataExtractionError(RuntimeError):
    """Raised when structured data cannot be extracted from a document."""


def extract_invoice_data(
    text: str,
    *,
    client: OpenAI | None = None,
    model: str | None = None,
) -> InvoiceData:
    """Extract invoice fields using OpenAI Structured Outputs."""

    if not text.strip():
        raise DataExtractionError("Cannot extract data from an empty document")

    load_dotenv()
    selected_model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    if client is None:
        if not os.getenv("OPENAI_API_KEY"):
            raise DataExtractionError(
                "OPENAI_API_KEY is not configured. Add it to the local .env file."
            )
        client = OpenAI()

    try:
        response = client.responses.parse(
            model=selected_model,
            instructions=(
                "Extract invoice data from the supplied document text. Return null "
                "for every field that is missing or uncertain. Do not infer or invent "
                "values. Preserve invoice numbers exactly. Use ISO 8601 YYYY-MM-DD "
                "for dates when the source provides an unambiguous date. Use a "
                "three-letter ISO currency code when identifiable. Return monetary "
                "values as numbers without currency symbols or thousands separators."
            ),
            input=text,
            text_format=InvoiceData,
        )
        result = response.output_parsed
        if result is None:
            raise DataExtractionError("The model returned no extracted invoice data")
        return result
    except DataExtractionError:
        raise
    except Exception as error:
        LOGGER.exception("Invoice data extraction failed")
        raise DataExtractionError(f"Invoice data extraction failed: {error}") from error
