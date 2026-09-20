"""Processing status decisions for documents moving through the pipeline."""

from dataclasses import dataclass
from enum import Enum

from app.data_extractor import InvoiceData
from app.validator import BusinessValidationResult

MIN_EXTRACTION_CONFIDENCE = 0.8


class ProcessingStatus(str, Enum):
    """Final state of a document processing attempt."""

    PROCESSED = "processed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


@dataclass(frozen=True)
class ProcessingDecision:
    """A document status together with human-readable reasons."""

    status: ProcessingStatus
    reasons: tuple[str, ...] = ()


def processed() -> ProcessingDecision:
    """Return a successful processing decision."""

    return ProcessingDecision(status=ProcessingStatus.PROCESSED)


def failed(reason: str) -> ProcessingDecision:
    """Return a technical failure decision."""

    return ProcessingDecision(status=ProcessingStatus.FAILED, reasons=(reason,))


def assess_invoice(
    extraction: InvoiceData,
    *,
    schema_error: str | None = None,
    business_validation: BusinessValidationResult | None = None,
) -> ProcessingDecision:
    """Choose processed or needs_review from data-quality signals."""

    reasons: list[str] = []

    if schema_error:
        reasons.append(schema_error)

    if extraction.confidence < MIN_EXTRACTION_CONFIDENCE:
        reasons.append(
            "extraction confidence "
            f"{extraction.confidence:.2f} is below {MIN_EXTRACTION_CONFIDENCE:.2f}"
        )

    if extraction.uncertain_fields:
        reasons.append(
            "uncertain extracted fields: " + ", ".join(extraction.uncertain_fields)
        )

    if business_validation is not None:
        reasons.extend(
            f"{issue.field}: {issue.message}"
            for issue in business_validation.issues
        )

    if reasons:
        return ProcessingDecision(
            status=ProcessingStatus.NEEDS_REVIEW,
            reasons=tuple(reasons),
        )
    return processed()
