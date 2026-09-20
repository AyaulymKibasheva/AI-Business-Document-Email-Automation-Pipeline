"""FastAPI interface for document processing and manual review."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict
from sqlalchemy.engine import Engine

from app.database import (
    DatabaseError,
    approve_document,
    calculate_file_hash,
    create_database_engine,
    database_url_from_env,
    get_document,
    get_document_by_hash,
    initialize_database,
    list_documents,
)
from app.main import process_document
from app.parser import SUPPORTED_EXTENSIONS

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
UPLOAD_DIRECTORY = Path("data/api_uploads")


class ExtractedDataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_number: str
    company: str
    date: str
    due_date: str | None
    currency: str
    subtotal: float | None
    tax: float | None
    total: float
    email: str | None


class DocumentResponse(BaseModel):
    id: int
    filename: str
    document_type: str | None
    status: str
    created_at: str
    processed_at: str
    extracted_data: ExtractedDataResponse | None
    reasons: list[str]
    duplicate: bool = False


def _engine_from_environment() -> Engine:
    database_url = database_url_from_env()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for the API")
    return create_database_engine(database_url)


def _response(document: dict, *, duplicate: bool = False) -> DocumentResponse:
    payload = dict(document)
    payload["created_at"] = document["created_at"].isoformat()
    payload["processed_at"] = document["processed_at"].isoformat()
    if payload["extracted_data"]:
        extracted = dict(payload["extracted_data"])
        extracted["date"] = extracted["date"].isoformat()
        if extracted["due_date"] is not None:
            extracted["due_date"] = extracted["due_date"].isoformat()
        payload["extracted_data"] = extracted
    payload["duplicate"] = duplicate
    return DocumentResponse.model_validate(payload)


def create_app(
    *,
    engine: Engine | None = None,
    processor: Callable[[str | Path], int] = process_document,
) -> FastAPI:
    """Build the API with injectable dependencies for integration tests."""

    database = engine or _engine_from_environment()
    initialize_database(database)
    app = FastAPI(
        title="AI Business Document Automation API",
        version="1.0.0",
    )
    app.state.engine = database

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/documents",
        response_model=DocumentResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def upload_document(file: UploadFile = File(...)) -> DocumentResponse:
        original_name = Path(file.filename or "document").name
        extension = Path(original_name).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail="Supported document types: PDF, DOCX, TXT",
            )

        UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
        destination = UPLOAD_DIRECTORY / f"{uuid4().hex}_{original_name}"
        size = 0
        try:
            with destination.open("wb") as target:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="File exceeds 20 MB")
                    target.write(chunk)
            file_hash = calculate_file_hash(destination)
            existing = get_document_by_hash(database, file_hash)
            if existing is not None:
                return _response(existing, duplicate=True)

            result_code = await run_in_threadpool(processor, destination)
            document = get_document_by_hash(database, file_hash)
            if document is None:
                raise HTTPException(
                    status_code=500,
                    detail=f"Processing finished with code {result_code} but no database record was created",
                )
            return _response(document)
        finally:
            await file.close()
            destination.unlink(missing_ok=True)

    @app.get("/documents", response_model=list[DocumentResponse])
    def documents(limit: int = Query(100, ge=1, le=500)) -> list[DocumentResponse]:
        return [_response(item) for item in list_documents(database, limit=limit)]

    @app.get("/documents/{document_id}", response_model=DocumentResponse)
    def document(document_id: int) -> DocumentResponse:
        item = get_document(database, document_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return _response(item)

    @app.get("/review", response_model=list[DocumentResponse])
    def review(limit: int = Query(100, ge=1, le=500)) -> list[DocumentResponse]:
        return [
            _response(item)
            for item in list_documents(database, status="needs_review", limit=limit)
        ]

    @app.post("/documents/{document_id}/approve", response_model=DocumentResponse)
    def approve(document_id: int) -> DocumentResponse:
        try:
            item = approve_document(database, document_id)
        except DatabaseError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if item is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return _response(item)

    return app
