"""Tests for structured AI document classification."""

import unittest
from types import SimpleNamespace
from unittest.mock import ANY, Mock
from unittest.mock import patch

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
        client.chat.return_value = SimpleNamespace(
            message=SimpleNamespace(content=expected.model_dump_json())
        )

        result = classify_document(
            "Invoice number INV-100. Total: 42 USD.",
            client=client,
            model="test-model",
        )

        self.assertEqual(result, expected)
        client.chat.assert_called_once_with(
            model="test-model",
            messages=[
                {"role": "system", "content": ANY},
                {
                    "role": "user",
                    "content": "Invoice number INV-100. Total: 42 USD.",
                },
            ],
            format=DocumentClassification.model_json_schema(),
            options={"temperature": 0},
        )

    def test_rejects_empty_text_without_api_call(self) -> None:
        client = Mock()

        with self.assertRaisesRegex(ClassificationError, "empty document"):
            classify_document("   ", client=client)

        client.chat.assert_not_called()

    def test_rejects_empty_model_response(self) -> None:
        client = Mock()
        client.chat.return_value = SimpleNamespace(
            message=SimpleNamespace(content="")
        )

        with self.assertRaisesRegex(ClassificationError, "empty response"):
            classify_document("Some document", client=client)

        client.chat.assert_called_once()

    def test_retries_transient_model_failure(self) -> None:
        expected = DocumentClassification(document_type=DocumentCategory.INVOICE)
        client = Mock()
        client.chat.side_effect = [
            ConnectionError("temporary"),
            SimpleNamespace(message=SimpleNamespace(content=expected.model_dump_json())),
        ]

        with patch.dict(
            "os.environ", {"AI_MAX_ATTEMPTS": "2", "AI_RETRY_BASE_SECONDS": "0"}
        ):
            result = classify_document("Invoice INV-17", client=client)

        self.assertEqual(result, expected)
        self.assertEqual(client.chat.call_count, 2)


if __name__ == "__main__":
    unittest.main()
