"""Command-line entry point for manual document uploads."""

import argparse
from collections.abc import Sequence

from app.classifier import ClassificationError, DocumentCategory, classify_document
from app.data_extractor import DataExtractionError, extract_invoice_data
from app.extractor import TextExtractionError, extract_text
from app.parser import receive_document
from app.status import ProcessingDecision, assess_invoice, failed, processed
from app.validator import (
    InvoiceSchemaError,
    validate_invoice_business_rules,
    validate_invoice_schema,
)


def print_decision(decision: ProcessingDecision) -> None:
    """Print a consistent final processing status."""

    print(f"\nStatus: {decision.status.value}")
    for reason in decision.reasons:
        print(f"- {reason}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upload a business document to the processing pipeline."
    )
    parser.add_argument("file", help="Path to a PDF, DOCX, or TXT document")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        document = receive_document(args.file)
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}")
        print_decision(failed(str(error)))
        return 1

    print(document.filename)
    print(f"-> {document.document_type.value} detected")
    print("-> ready for processing")

    try:
        text = extract_text(document)
    except TextExtractionError as error:
        print(f"Error: {error}")
        print_decision(failed(str(error)))
        return 1

    print("-> text extracted")
    print("\nDocument text:\n")
    print(text)

    try:
        classification = classify_document(text)
    except ClassificationError as error:
        print(f"Error: {error}")
        print_decision(failed(str(error)))
        return 1

    print("\nDocument classification:\n")
    print(classification.model_dump_json(indent=2))

    if classification.document_type == DocumentCategory.INVOICE:
        try:
            invoice = extract_invoice_data(text)
        except DataExtractionError as error:
            print(f"Error: {error}")
            print_decision(failed(str(error)))
            return 1

        print("\nExtracted invoice data:\n")
        print(invoice.model_dump_json(indent=2))

        try:
            validated_invoice = validate_invoice_schema(invoice)
        except InvoiceSchemaError as error:
            decision = assess_invoice(invoice, schema_error=str(error))
            print_decision(decision)
            return 2

        print("\n-> Pydantic schema validation passed")
        validation = validate_invoice_business_rules(validated_invoice)
        decision = assess_invoice(invoice, business_validation=validation)
        if decision.status.value == "needs_review":
            print("-> business rules or confidence review required")
            print_decision(decision)
            return 2

        print("-> business rules validation passed")
        print_decision(decision)
    else:
        print("\n-> structured extraction is not available for this document type yet")
        print_decision(processed())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
