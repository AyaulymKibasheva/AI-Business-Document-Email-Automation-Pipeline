"""Tests for stage 13 Google Sheets synchronization."""

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app.sheets_writer import (
    SHEET_HEADERS,
    GoogleSheetsConfig,
    GoogleSheetsError,
    append_invoice_row,
)
from app.validator import Invoice


class FakeWorksheet:
    def __init__(self, headers=None) -> None:
        self.headers = headers or []
        self.updates = []
        self.rows = []

    def row_values(self, row: int):
        return self.headers

    def update(self, cell_range, values):
        self.updates.append((cell_range, values))

    def append_row(self, values, value_input_option):
        self.rows.append((values, value_input_option))


class FakeSpreadsheet:
    def __init__(self, worksheet) -> None:
        self.sheet = worksheet

    def worksheet(self, title):
        return self.sheet


class FakeClient:
    def __init__(self, worksheet) -> None:
        self.sheet = worksheet

    def open_by_key(self, spreadsheet_id):
        return FakeSpreadsheet(self.sheet)


class GoogleSheetsWriterTests(unittest.TestCase):
    def _invoice(self) -> Invoice:
        return Invoice(
            invoice_number="INV-13",
            company_name="Sheets Ltd",
            invoice_date=date(2026, 9, 20),
            due_date=None,
            currency="USD",
            subtotal=80,
            tax=20,
            total=100,
            email="billing@sheets.example",
        )

    def test_appends_invoice_and_initializes_headers(self) -> None:
        worksheet = FakeWorksheet()
        config = GoogleSheetsConfig(Path("credentials.json"), "sheet-id")

        append_invoice_row(
            config,
            self._invoice(),
            "processed",
            client_factory=lambda **kwargs: FakeClient(worksheet),
        )

        self.assertEqual(worksheet.updates, [("A1:F1", [SHEET_HEADERS])])
        self.assertEqual(
            worksheet.rows[0][0],
            ["INV-13", "Sheets Ltd", "2026-09-20", 100.0, "USD", "processed"],
        )
        self.assertEqual(worksheet.rows[0][1], "USER_ENTERED")

    def test_configuration_is_optional_when_no_values_are_set(self) -> None:
        with patch.dict("os.environ", {}, clear=True), patch(
            "app.sheets_writer.load_dotenv"
        ):
            self.assertIsNone(GoogleSheetsConfig.from_env())

    def test_rejects_partial_configuration(self) -> None:
        with patch.dict(
            "os.environ", {"GOOGLE_SHEETS_SPREADSHEET_ID": "sheet-id"}, clear=True
        ), patch("app.sheets_writer.load_dotenv"):
            with self.assertRaises(GoogleSheetsError):
                GoogleSheetsConfig.from_env()


if __name__ == "__main__":
    unittest.main()
