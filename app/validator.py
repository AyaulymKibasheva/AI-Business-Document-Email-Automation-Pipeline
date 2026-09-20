"""Schema and business-rule validation for extracted document data."""

import re
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, ConfigDict, ValidationError

from app.data_extractor import InvoiceData


class Invoice(BaseModel):
    """Strict normalized invoice schema used by the processing pipeline."""

    model_config = ConfigDict(strict=True, extra="forbid")

    invoice_number: str
    company_name: str
    invoice_date: date
    due_date: date | None
    currency: str
    subtotal: float | None
    tax: float | None
    total: float
    email: str | None


class InvoiceSchemaError(ValueError):
    """Raised when AI-extracted data does not match the invoice schema."""


@dataclass(frozen=True)
class ValidationIssue:
    """A single failed business rule."""

    field: str
    message: str


@dataclass(frozen=True)
class BusinessValidationResult:
    """Result of deterministic invoice business-rule validation."""

    issues: tuple[ValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not self.issues


ALLOWED_CURRENCIES = frozenset(
    {
        "AUD",
        "CAD",
        "CHF",
        "CNY",
        "EUR",
        "GBP",
        "JPY",
        "KZT",
        "RUB",
        "USD",
    }
)

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def validate_invoice_schema(extracted: InvoiceData) -> Invoice:
    """Convert extracted data to the strict invoice schema."""

    try:
        # JSON validation keeps strict typing while allowing ISO date strings,
        # which are the natural JSON representation of calendar dates.
        return Invoice.model_validate_json(
            extracted.model_dump_json(exclude={"confidence", "uncertain_fields"})
        )
    except ValidationError as error:
        details = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors()
        )
        raise InvoiceSchemaError(f"Invoice schema validation failed: {details}") from error


def validate_invoice_business_rules(invoice: Invoice) -> BusinessValidationResult:
    """Validate invoice values using deterministic Python rules only."""

    issues: list[ValidationIssue] = []

    if not invoice.invoice_number.strip():
        issues.append(ValidationIssue("invoice_number", "must not be empty"))

    if not invoice.company_name.strip():
        issues.append(ValidationIssue("company_name", "must not be empty"))

    if invoice.total <= 0:
        issues.append(ValidationIssue("total", "must be greater than zero"))

    if invoice.currency not in ALLOWED_CURRENCIES:
        issues.append(
            ValidationIssue(
                "currency",
                f"must be one of: {', '.join(sorted(ALLOWED_CURRENCIES))}",
            )
        )

    if invoice.email is not None and not EMAIL_PATTERN.fullmatch(invoice.email):
        issues.append(ValidationIssue("email", "must be a valid email address"))

    if invoice.due_date is not None and invoice.due_date < invoice.invoice_date:
        issues.append(
            ValidationIssue("due_date", "must not be earlier than invoice_date")
        )

    if invoice.subtotal is not None and invoice.subtotal < 0:
        issues.append(ValidationIssue("subtotal", "must not be negative"))

    if invoice.tax is not None and invoice.tax < 0:
        issues.append(ValidationIssue("tax", "must not be negative"))

    if invoice.subtotal is not None and invoice.tax is not None:
        expected_total = invoice.subtotal + invoice.tax
        if abs(expected_total - invoice.total) > 0.01:
            issues.append(
                ValidationIssue(
                    "total",
                    "must equal subtotal plus tax within a 0.01 tolerance",
                )
            )

    return BusinessValidationResult(issues=tuple(issues))
