"""Tests for schema and business-rule invoice validation."""

import unittest
from datetime import date

from app.data_extractor import InvoiceData
from app.validator import (
    Invoice,
    InvoiceSchemaError,
    validate_invoice_business_rules,
    validate_invoice_schema,
)


def valid_extracted_invoice(**overrides: object) -> InvoiceData:
    values = {
        "invoice_number": "INV-1048",
        "company_name": "ABC Ltd",
        "invoice_date": "2026-09-15",
        "due_date": "2026-10-15",
        "currency": "USD",
        "subtotal": 1000.0,
        "tax": 250.0,
        "total": 1250.0,
        "email": "billing@example.com",
    }
    values.update(overrides)
    return InvoiceData.model_validate(values)


class InvoiceSchemaTests(unittest.TestCase):
    def test_normalizes_iso_dates_to_date_objects(self) -> None:
        invoice = validate_invoice_schema(valid_extracted_invoice())

        self.assertEqual(invoice.invoice_date, date(2026, 9, 15))
        self.assertEqual(invoice.due_date, date(2026, 10, 15))

    def test_rejects_missing_required_field(self) -> None:
        with self.assertRaisesRegex(InvoiceSchemaError, "invoice_number"):
            validate_invoice_schema(valid_extracted_invoice(invoice_number=None))

    def test_rejects_invalid_calendar_date(self) -> None:
        with self.assertRaisesRegex(InvoiceSchemaError, "invoice_date"):
            validate_invoice_schema(valid_extracted_invoice(invoice_date="2026-02-30"))


class InvoiceBusinessRuleTests(unittest.TestCase):
    def test_accepts_valid_invoice(self) -> None:
        result = validate_invoice_business_rules(
            validate_invoice_schema(valid_extracted_invoice())
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.issues, ())

    def test_reports_all_invalid_business_values(self) -> None:
        invoice = Invoice(
            invoice_number=" ",
            company_name=" ",
            invoice_date=date(2026, 9, 15),
            due_date=date(2026, 9, 1),
            currency="BTC",
            subtotal=-10.0,
            tax=-2.0,
            total=-5.0,
            email="not-an-email",
        )

        result = validate_invoice_business_rules(invoice)
        invalid_fields = [issue.field for issue in result.issues]

        self.assertFalse(result.is_valid)
        self.assertIn("invoice_number", invalid_fields)
        self.assertIn("company_name", invalid_fields)
        self.assertIn("total", invalid_fields)
        self.assertIn("currency", invalid_fields)
        self.assertIn("email", invalid_fields)
        self.assertIn("due_date", invalid_fields)
        self.assertIn("subtotal", invalid_fields)
        self.assertIn("tax", invalid_fields)

    def test_rejects_total_mismatch(self) -> None:
        invoice = validate_invoice_schema(valid_extracted_invoice(total=1200.0))

        result = validate_invoice_business_rules(invoice)

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("subtotal plus tax" in issue.message for issue in result.issues)
        )


if __name__ == "__main__":
    unittest.main()
