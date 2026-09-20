"""Integration tests for the stage 16 FastAPI interface."""

import tempfile
import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api import create_app
from app.database import (
    calculate_file_hash,
    save_processing_result,
)
from app.status import ProcessingDecision, ProcessingStatus, processed


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        def processor(path):
            save_processing_result(
                self.engine,
                filename=path.name,
                file_hash=calculate_file_hash(path),
                document_type="other",
                decision=processed(),
                started_at=datetime.now(timezone.utc),
                stage="complete",
            )
            return 0

        self.client = TestClient(create_app(engine=self.engine, processor=processor))

    def tearDown(self) -> None:
        self.client.close()
        self.engine.dispose()

    def test_health(self) -> None:
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})

    def test_upload_list_get_and_duplicate(self) -> None:
        first = self.client.post(
            "/documents", files={"file": ("notes.txt", b"meeting notes", "text/plain")}
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["status"], "processed")

        duplicate = self.client.post(
            "/documents", files={"file": ("copy.txt", b"meeting notes", "text/plain")}
        )
        self.assertEqual(duplicate.status_code, 201)
        self.assertTrue(duplicate.json()["duplicate"])

        documents = self.client.get("/documents").json()
        self.assertEqual(len(documents), 1)
        document_id = documents[0]["id"]
        self.assertEqual(self.client.get(f"/documents/{document_id}").status_code, 200)

    def test_rejects_unsupported_upload(self) -> None:
        response = self.client.post(
            "/documents", files={"file": ("image.png", b"png", "image/png")}
        )
        self.assertEqual(response.status_code, 415)

    def test_review_queue_and_approval(self) -> None:
        decision = ProcessingDecision(
            ProcessingStatus.NEEDS_REVIEW, ("manual check",)
        )
        document_id = save_processing_result(
            self.engine,
            filename="review.txt",
            file_hash="r" * 64,
            document_type="invoice",
            decision=decision,
            started_at=datetime.now(timezone.utc),
            stage="business_validation",
        )

        review = self.client.get("/review").json()
        self.assertEqual([item["id"] for item in review], [document_id])

        approved = self.client.post(f"/documents/{document_id}/approve")
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["status"], "processed")
        self.assertEqual(self.client.get("/review").json(), [])

    def test_missing_document_is_404(self) -> None:
        self.assertEqual(self.client.get("/documents/999").status_code, 404)
        self.assertEqual(
            self.client.post("/documents/999/approve").status_code, 404
        )


if __name__ == "__main__":
    unittest.main()
