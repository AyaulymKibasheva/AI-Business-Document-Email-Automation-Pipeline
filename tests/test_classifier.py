"""Tests for structured AI document classification."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from app.classifier import (
    ClassificationError,
    DocumentCategory,
    DocumentClassification,
    classify_document,
)


class ClassifyDocumentTests(unittest.TestCase):
    def test_returns_structured_classification(self) -> None:
        expected = DocumentClassification(document_type=DocumentCategory.INVOICE)
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(output_parsed=expected)

        result = classify_document(
            "Invoice number INV-100. Total: 42 USD.",
            client=client,
            model="test-model",
        )

        self.assertEqual(result, expected)
        client.responses.parse.assert_called_once_with(
            model="test-model",
            instructions=unittest.mock.ANY,
            input="Invoice number INV-100. Total: 42 USD.",
            text_format=DocumentClassification,
        )

    def test_rejects_empty_text_without_api_call(self) -> None:
        client = Mock()

        with self.assertRaisesRegex(ClassificationError, "empty document"):
            classify_document("   ", client=client)

        client.responses.parse.assert_not_called()

    def test_rejects_missing_parsed_output(self) -> None:
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(output_parsed=None)

        with self.assertRaisesRegex(ClassificationError, "no classification"):
            classify_document("Some document", client=client)


if __name__ == "__main__":
    unittest.main()
