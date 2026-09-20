"""Tests for AI-powered structured invoice extraction."""

import unittest
from types import SimpleNamespace
from unittest.mock import ANY, Mock

from app.data_extractor import DataExtractionError, InvoiceData, extract_invoice_data


class ExtractInvoiceDataTests(unittest.TestCase):
    def test_returns_structured_invoice_data(self) -> None:
        expected = InvoiceData(
            invoice_number="INV-1048",
            company_name="ABC Ltd",
            invoice_date="2026-09-15",
            due_date="2026-10-15",
            currency="USD",
            subtotal=1000.0,
            tax=250.0,
            total=1250.0,
            email="billing@example.com",
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(output_parsed=expected)

        result = extract_invoice_data(
            "Invoice INV-1048 from ABC Ltd. Total USD 1,250.00.",
            client=client,
            model="test-model",
        )

        self.assertEqual(result, expected)
        client.responses.parse.assert_called_once_with(
            model="test-model",
            instructions=ANY,
            input="Invoice INV-1048 from ABC Ltd. Total USD 1,250.00.",
            text_format=InvoiceData,
        )

    def test_allows_missing_source_fields(self) -> None:
        invoice = InvoiceData(
            invoice_number="INV-1",
            company_name=None,
            invoice_date=None,
            due_date=None,
            currency=None,
            subtotal=None,
            tax=None,
            total=None,
            email=None,
        )

        self.assertIsNone(invoice.total)

    def test_rejects_empty_text_without_api_call(self) -> None:
        client = Mock()

        with self.assertRaisesRegex(DataExtractionError, "empty document"):
            extract_invoice_data("  ", client=client)

        client.responses.parse.assert_not_called()

    def test_rejects_missing_parsed_output(self) -> None:
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(output_parsed=None)

        with self.assertRaisesRegex(DataExtractionError, "no extracted invoice data"):
            extract_invoice_data("Invoice text", client=client)


if __name__ == "__main__":
    unittest.main()
