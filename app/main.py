"""Command-line entry point for manual document uploads."""

import argparse
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

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
from app.email_reader import EmailConfig, EmailIngestionError, download_unread_attachments
from app.parser import SUPPORTED_EXTENSIONS, receive_document
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
        description="Process one business document or every supported file in a folder."
    )
    parser.add_argument(
        "path", nargs="?", help="Path to a PDF, DOCX, TXT document, or folder"
    )
    parser.add_argument(
        "--email",
        action="store_true",
        help="Download unread email attachments and process them",
    )
    return parser


def process_document(file_path: str | Path) -> int:
    """Process one document and return 0, 1, or 2 for its final status."""

    started_at = datetime.now(timezone.utc)

    try:
        document = receive_document(file_path)
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


def discover_documents(directory: str | Path) -> list[Path]:
    """Return supported files in a directory in stable filename order."""

    root = Path(directory)
    return sorted(
        (
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=lambda path: path.name.lower(),
    )


def process_documents(documents: Sequence[Path], *, source: str = "Batch") -> int:
    """Process paths without letting one document failure stop the group."""

    if not documents:
        print("No new supported PDF, DOCX, or TXT documents found.")
        return 1

    counts = {"processed": 0, "needs_review": 0, "failed": 0}
    print(f"{source} processing: {len(documents)} document(s) received")

    for index, path in enumerate(documents, start=1):
        print(f"\n{'=' * 72}")
        print(f"[{index}/{len(documents)}] {path.name}")
        print("=" * 72)
        try:
            result = process_document(path)
        except Exception as error:
            # A defensive boundary keeps unexpected failures isolated per file.
            print(f"Unexpected error: {error}")
            result = 1

        if result == 0:
            counts["processed"] += 1
        elif result == 2:
            counts["needs_review"] += 1
        else:
            counts["failed"] += 1

    print("\nBatch summary")
    print(f"{len(documents)} received")
    print(f"{counts['processed']} processed")
    print(f"{counts['needs_review']} needs review")
    print(f"{counts['failed']} failed")
    return 1 if counts["failed"] else 0


def process_batch(directory: str | Path) -> int:
    """Process all supported files in a directory."""

    return process_documents(discover_documents(directory))


def process_email() -> int:
    """Download new inbox attachments and send them through the pipeline."""

    try:
        documents = download_unread_attachments(EmailConfig.from_env())
    except EmailIngestionError as error:
        print(f"Email error: {error}")
        return 1
    return process_documents(documents, source="Email")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.email:
        if args.path:
            print("Error: path cannot be combined with --email")
            return 1
        return process_email()
    if not args.path:
        print("Error: provide a document path or use --email")
        return 1
    path = Path(args.path).expanduser()
    if path.is_dir():
        return process_batch(path)
    return process_document(path)


if __name__ == "__main__":
    raise SystemExit(main())
