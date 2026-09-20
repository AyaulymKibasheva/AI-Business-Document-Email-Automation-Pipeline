"""Tests for manual document intake."""

import tempfile
import unittest
from pathlib import Path

from app.parser import DocumentType, UnsupportedDocumentError, receive_document


class ReceiveDocumentTests(unittest.TestCase):
    def test_detects_all_supported_types_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename, expected_type in (
                ("invoice.PDF", DocumentType.PDF),
                ("order.docx", DocumentType.DOCX),
                ("notes.txt", DocumentType.TXT),
            ):
                path = root / filename
                path.touch()
                with self.subTest(filename=filename):
                    self.assertEqual(receive_document(path).document_type, expected_type)

    def test_rejects_unsupported_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.png"
            path.touch()
            with self.assertRaises(UnsupportedDocumentError):
                receive_document(path)

    def test_rejects_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            receive_document("missing.pdf")


if __name__ == "__main__":
    unittest.main()
