"""Tests for the stage 20 demonstration helper."""

import tempfile
import unittest
from pathlib import Path

from scripts.demo_workflow import multipart_body, print_result


class DemoWorkflowTests(unittest.TestCase):
    def test_multipart_body_contains_file_and_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sample = Path(directory) / "invoice.txt"
            sample.write_text("Invoice DEMO-1", encoding="utf-8")

            body, content_type = multipart_body(sample)

        self.assertIn("multipart/form-data; boundary=", content_type)
        self.assertIn(b'filename="invoice.txt"', body)
        self.assertIn(b"Invoice DEMO-1", body)
        boundary = content_type.split("boundary=", 1)[1].encode()
        self.assertTrue(body.startswith(b"--" + boundary))
        self.assertTrue(body.endswith(b"--\r\n"))

    def test_print_result_accepts_missing_optional_values(self) -> None:
        print_result("Result", {"id": 1, "status": "processed"})


if __name__ == "__main__":
    unittest.main()

