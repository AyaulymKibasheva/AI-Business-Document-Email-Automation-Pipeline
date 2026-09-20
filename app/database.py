"""SQLAlchemy persistence for document processing results."""

import hashlib
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    or_,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from app.status import ProcessingDecision
from app.validator import Invoice


class Base(DeclarativeBase):
    """Base class for all database models."""


class DocumentRecord(Base):
    """A document received by the processing pipeline."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    document_type: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    extracted_data: Mapped["ExtractedDataRecord | None"] = relationship(
        back_populates="document", cascade="all, delete-orphan", uselist=False
    )
    processing_runs: Mapped[list["ProcessingRunRecord"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    errors: Mapped[list["ErrorRecord"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class ExtractedDataRecord(Base):
    """Normalized invoice data extracted from a document."""

    __tablename__ = "extracted_data"
    __table_args__ = (
        UniqueConstraint(
            "invoice_number", "company", name="uq_invoice_number_company"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    tax: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))

    document: Mapped[DocumentRecord] = relationship(back_populates="extracted_data")


class ProcessingRunRecord(Base):
    """One processing attempt for a document."""

    __tablename__ = "processing_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    uncertain_fields: Mapped[list[str] | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    document: Mapped[DocumentRecord] = relationship(back_populates="processing_runs")
    errors: Mapped[list["ErrorRecord"]] = relationship(
        back_populates="processing_run", cascade="all, delete-orphan"
    )


class ErrorRecord(Base):
    """A technical failure or review reason recorded during processing."""

    __tablename__ = "errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    processing_run_id: Mapped[int] = mapped_column(
        ForeignKey("processing_runs.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[DocumentRecord] = relationship(back_populates="errors")
    processing_run: Mapped[ProcessingRunRecord] = relationship(back_populates="errors")


class DatabaseError(RuntimeError):
    """Raised when a database operation cannot be completed."""


class DuplicateDocumentError(DatabaseError):
    """Raised when a file or logical invoice has already been stored."""

    def __init__(self, document_id: int) -> None:
        self.document_id = document_id
        super().__init__(f"Duplicate document detected (existing id: {document_id})")


def calculate_file_hash(file_path: str | Path) -> str:
    """Return a SHA-256 hash without loading the whole file into memory."""

    digest = hashlib.sha256()
    with Path(file_path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_duplicate_document(
    engine: Engine,
    *,
    file_hash: str,
    invoice_number: str | None = None,
    company: str | None = None,
) -> int | None:
    """Find an existing document by file hash or invoice identity."""

    with Session(engine) as session:
        by_hash = session.scalar(
            select(DocumentRecord.id).where(DocumentRecord.file_hash == file_hash)
        )
        if by_hash is not None:
            return by_hash

        if invoice_number and company:
            return session.scalar(
                select(ExtractedDataRecord.document_id).where(
                    ExtractedDataRecord.invoice_number == invoice_number,
                    ExtractedDataRecord.company == company,
                )
            )
    return None


def create_database_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine for MySQL or an isolated test database."""

    return create_engine(database_url, pool_pre_ping=True)


def initialize_database(engine: Engine) -> None:
    """Create all pipeline tables that do not already exist."""

    Base.metadata.create_all(engine)


def database_url_from_env() -> str | None:
    """Return the configured database URL, if persistence is enabled."""

    load_dotenv()
    return os.getenv("DATABASE_URL") or None


def save_processing_result(
    engine: Engine,
    *,
    filename: str | Path,
    file_hash: str,
    document_type: str | None,
    decision: ProcessingDecision,
    started_at: datetime,
    stage: str,
    invoice: Invoice | None = None,
    confidence: float | None = None,
    uncertain_fields: list[str] | None = None,
    model_name: str | None = None,
) -> int:
    """Atomically store a document, run, extracted invoice, and any reasons."""

    completed_at = datetime.now(timezone.utc)
    try:
        with Session(engine) as session, session.begin():
            duplicate_id = session.scalar(
                select(DocumentRecord.id)
                .outerjoin(ExtractedDataRecord)
                .where(
                    or_(
                        DocumentRecord.file_hash == file_hash,
                        (
                            (ExtractedDataRecord.invoice_number == invoice.invoice_number)
                            & (ExtractedDataRecord.company == invoice.company_name)
                            if invoice is not None
                            else False
                        ),
                    )
                )
                .limit(1)
            )
            if duplicate_id is not None:
                raise DuplicateDocumentError(duplicate_id)

            document = DocumentRecord(
                filename=Path(filename).name,
                file_hash=file_hash,
                document_type=document_type,
                status=decision.status.value,
                processed_at=completed_at,
            )
            session.add(document)
            session.flush()

            run = ProcessingRunRecord(
                document_id=document.id,
                status=decision.status.value,
                model_name=model_name,
                confidence=confidence,
                uncertain_fields=uncertain_fields,
                started_at=started_at,
                completed_at=completed_at,
            )
            session.add(run)
            session.flush()

            if invoice is not None:
                session.add(
                    ExtractedDataRecord(
                        document_id=document.id,
                        invoice_number=invoice.invoice_number,
                        company=invoice.company_name,
                        invoice_date=invoice.invoice_date,
                        due_date=invoice.due_date,
                        currency=invoice.currency,
                        subtotal=invoice.subtotal,
                        tax=invoice.tax,
                        total=invoice.total,
                        email=invoice.email,
                    )
                )

            session.add_all(
                ErrorRecord(
                    document_id=document.id,
                    processing_run_id=run.id,
                    stage=stage,
                    message=reason,
                )
                for reason in decision.reasons
            )
            session.flush()
            document_id = document.id
        return document_id
    except DuplicateDocumentError:
        raise
    except SQLAlchemyError as error:
        raise DatabaseError(f"Could not save processing result: {error}") from error


def count_records(engine: Engine) -> dict[str, int]:
    """Return table counts for diagnostics and tests."""

    models: dict[str, type[Base]] = {
        "documents": DocumentRecord,
        "extracted_data": ExtractedDataRecord,
        "processing_runs": ProcessingRunRecord,
        "errors": ErrorRecord,
    }
    with Session(engine) as session:
        return {
            name: len(session.scalars(select(model)).all())
            for name, model in models.items()
        }


def _document_dict(document: DocumentRecord) -> dict:
    """Serialize a document and its normalized invoice for API responses."""

    extracted = document.extracted_data
    return {
        "id": document.id,
        "filename": document.filename,
        "document_type": document.document_type,
        "status": document.status,
        "created_at": document.created_at,
        "processed_at": document.processed_at,
        "extracted_data": (
            {
                "invoice_number": extracted.invoice_number,
                "company": extracted.company,
                "date": extracted.invoice_date,
                "due_date": extracted.due_date,
                "currency": extracted.currency,
                "subtotal": float(extracted.subtotal) if extracted.subtotal is not None else None,
                "tax": float(extracted.tax) if extracted.tax is not None else None,
                "total": float(extracted.total),
                "email": extracted.email,
            }
            if extracted is not None
            else None
        ),
        "reasons": [error.message for error in document.errors],
    }


def get_document(engine: Engine, document_id: int) -> dict | None:
    """Return one document with extracted data and review reasons."""

    with Session(engine) as session:
        document = session.get(DocumentRecord, document_id)
        return _document_dict(document) if document is not None else None


def get_document_by_hash(engine: Engine, file_hash: str) -> dict | None:
    """Return a document by its immutable file hash."""

    with Session(engine) as session:
        document = session.scalar(
            select(DocumentRecord).where(DocumentRecord.file_hash == file_hash)
        )
        return _document_dict(document) if document is not None else None


def list_documents(
    engine: Engine, *, status: str | None = None, limit: int = 100
) -> list[dict]:
    """List newest documents, optionally filtered by processing status."""

    statement = select(DocumentRecord).order_by(DocumentRecord.id.desc()).limit(limit)
    if status is not None:
        statement = statement.where(DocumentRecord.status == status)
    with Session(engine) as session:
        return [_document_dict(document) for document in session.scalars(statement)]


def approve_document(engine: Engine, document_id: int) -> dict | None:
    """Move a needs-review document to processed and record the manual action."""

    now = datetime.now(timezone.utc)
    try:
        with Session(engine) as session, session.begin():
            document = session.get(DocumentRecord, document_id)
            if document is None:
                return None
            if document.status != "needs_review":
                raise DatabaseError(
                    f"Only needs_review documents can be approved (current: {document.status})"
                )
            document.status = "processed"
            document.processed_at = now
            session.add(
                ProcessingRunRecord(
                    document_id=document.id,
                    status="processed",
                    model_name=None,
                    confidence=None,
                    uncertain_fields=None,
                    started_at=now,
                    completed_at=now,
                )
            )
        return get_document(engine, document_id)
    except DatabaseError:
        raise
    except SQLAlchemyError as error:
        raise DatabaseError(f"Could not approve document: {error}") from error


def dashboard_metrics(engine: Engine) -> dict:
    """Return exact aggregate metrics for the Streamlit dashboard."""

    with Session(engine) as session:
        statuses = {
            status: session.scalar(
                select(func.count(DocumentRecord.id)).where(
                    DocumentRecord.status == status
                )
            )
            or 0
            for status in ("processed", "needs_review", "failed")
        }
        total_documents = session.scalar(select(func.count(DocumentRecord.id))) or 0
        total_amount = session.scalar(select(func.sum(ExtractedDataRecord.total))) or 0
        last_run = session.scalar(select(func.max(ProcessingRunRecord.completed_at)))
    return {
        "total_documents": int(total_documents),
        **{name: int(value) for name, value in statuses.items()},
        "total_invoice_amount": float(total_amount),
        "last_processing_run": last_run,
    }
