"""Tests for plain-text document extraction."""

import tempfile
import unittest
from pathlib import Path

from app.extractor import TextExtractionError, extract_text
from app.parser import receive_document


class ExtractTextTests(unittest.TestCase):
    def test_extracts_txt_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.txt"
            path.write_text("Invoice notes", encoding="utf-8")

            self.assertEqual(extract_text(receive_document(path)), "Invoice notes")

    def test_extracts_docx_paragraphs(self) -> None:
        from docx import Document

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invoice.docx"
            document = Document()
            document.add_paragraph("Invoice INV-100")
            document.add_paragraph("Total: 42 USD")
            document.save(path)

            self.assertEqual(
                extract_text(receive_document(path)),
                "Invoice INV-100\nTotal: 42 USD",
            )

    def test_extracts_pdf_text(self) -> None:
        import pymupdf

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invoice.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text((72, 72), "Invoice INV-200")
            document.save(path)
            document.close()

            self.assertIn("Invoice INV-200", extract_text(receive_document(path)))

    def test_rejects_empty_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.txt"
            path.touch()

            with self.assertRaises(TextExtractionError):
                extract_text(receive_document(path))


if __name__ == "__main__":
    unittest.main()
