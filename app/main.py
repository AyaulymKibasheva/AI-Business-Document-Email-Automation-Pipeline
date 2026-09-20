"""Command-line entry point for manual document uploads."""

import argparse
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy.engine import Engine

from app.classifier import ClassificationError, DocumentCategory, classify_document
from app.database import (
    DatabaseError,
    DuplicateDocumentError,
    calculate_file_hash,
    create_database_engine,
    database_url_from_env,
    find_duplicate_document,
    initialize_database,
    save_processing_result,
)
from app.data_extractor import DataExtractionError, extract_invoice_data
from app.extractor import TextExtractionError, extract_text
from app.parser import receive_document
from app.local_ai import DEFAULT_MODEL
from app.status import ProcessingDecision, assess_invoice, failed, processed
from app.validator import (
    Invoice,
    InvoiceSchemaError,
    validate_invoice_business_rules,
    validate_invoice_schema,
)


def print_decision(decision: ProcessingDecision) -> None:
    """Print a consistent final processing status."""

    print(f"\nStatus: {decision.status.value}")
    for reason in decision.reasons:
        print(f"- {reason}")


def save_result(
    engine: Engine | None,
    *,
    filename: str,
    file_hash: str,
    document_type: str | None,
    decision: ProcessingDecision,
    started_at: datetime,
    stage: str,
    invoice: Invoice | None = None,
    confidence: float | None = None,
    uncertain_fields: list[str] | None = None,
) -> bool:
    """Persist a result when MySQL is configured; report duplicate detection."""

    if engine is None:
        return True
    try:
        document_id = save_processing_result(
            engine,
            filename=filename,
            file_hash=file_hash,
            document_type=document_type,
            decision=decision,
            started_at=started_at,
            stage=stage,
            invoice=invoice,
            confidence=confidence,
            uncertain_fields=uncertain_fields,
            model_name=DEFAULT_MODEL,
        )
        print(f"-> saved to database with id {document_id}")
        return True
    except DuplicateDocumentError as error:
        print(str(error))
        return False
    except DatabaseError as error:
        print(f"Database error: {error}")
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upload a business document to the processing pipeline."
    )
    parser.add_argument("file", help="Path to a PDF, DOCX, or TXT document")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    started_at = datetime.now(timezone.utc)

    try:
        document = receive_document(args.file)
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}")
        print_decision(failed(str(error)))
        return 1

    print(document.filename)
    print(f"-> {document.document_type.value} detected")
    print("-> ready for processing")

    file_hash = calculate_file_hash(document.path)
    engine = None
    database_url = database_url_from_env()
    if database_url:
        try:
            engine = create_database_engine(database_url)
            initialize_database(engine)
            duplicate_id = find_duplicate_document(engine, file_hash=file_hash)
            if duplicate_id is not None:
                print(f"Duplicate document detected (existing id: {duplicate_id})")
                return 0
        except Exception as error:
            print_decision(failed(f"Database initialization failed: {error}"))
            return 1

    try:
        text = extract_text(document)
    except TextExtractionError as error:
        print(f"Error: {error}")
        decision = failed(str(error))
        print_decision(decision)
        save_result(
            engine,
            filename=document.filename,
            file_hash=file_hash,
            document_type=None,
            decision=decision,
            started_at=started_at,
            stage="text_extraction",
        )
        return 1

    print("-> text extracted")
    print("\nDocument text:\n")
    print(text)

    try:
        classification = classify_document(text)
    except ClassificationError as error:
        print(f"Error: {error}")
        decision = failed(str(error))
        print_decision(decision)
        save_result(
            engine,
            filename=document.filename,
            file_hash=file_hash,
            document_type=None,
            decision=decision,
            started_at=started_at,
            stage="classification",
        )
        return 1

    print("\nDocument classification:\n")
    print(classification.model_dump_json(indent=2))

    if classification.document_type == DocumentCategory.INVOICE:
        try:
            invoice = extract_invoice_data(text)
        except DataExtractionError as error:
            print(f"Error: {error}")
            decision = failed(str(error))
            print_decision(decision)
            save_result(
                engine,
                filename=document.filename,
                file_hash=file_hash,
                document_type=classification.document_type.value,
                decision=decision,
                started_at=started_at,
                stage="data_extraction",
            )
            return 1

        print("\nExtracted invoice data:\n")
        print(invoice.model_dump_json(indent=2))

        try:
            validated_invoice = validate_invoice_schema(invoice)
        except InvoiceSchemaError as error:
            decision = assess_invoice(invoice, schema_error=str(error))
            print_decision(decision)
            save_result(
                engine,
                filename=document.filename,
                file_hash=file_hash,
                document_type=classification.document_type.value,
                decision=decision,
                started_at=started_at,
                stage="schema_validation",
                confidence=invoice.confidence,
                uncertain_fields=invoice.uncertain_fields,
            )
            return 2

        print("\n-> Pydantic schema validation passed")
        validation = validate_invoice_business_rules(validated_invoice)
        decision = assess_invoice(invoice, business_validation=validation)
        if decision.status.value == "needs_review":
            print("-> business rules or confidence review required")
            print_decision(decision)
            save_result(
                engine,
                filename=document.filename,
                file_hash=file_hash,
                document_type=classification.document_type.value,
                decision=decision,
                started_at=started_at,
                stage="business_validation",
                invoice=validated_invoice,
                confidence=invoice.confidence,
                uncertain_fields=invoice.uncertain_fields,
            )
            return 2

        print("-> business rules validation passed")
        print_decision(decision)
        if not save_result(
            engine,
            filename=document.filename,
            file_hash=file_hash,
            document_type=classification.document_type.value,
            decision=decision,
            started_at=started_at,
            stage="complete",
            invoice=validated_invoice,
            confidence=invoice.confidence,
            uncertain_fields=invoice.uncertain_fields,
        ):
            return 1
    else:
        print("\n-> structured extraction is not available for this document type yet")
        decision = processed()
        print_decision(decision)
        if not save_result(
            engine,
            filename=document.filename,
            file_hash=file_hash,
            document_type=classification.document_type.value,
            decision=decision,
            started_at=started_at,
            stage="complete",
        ):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
