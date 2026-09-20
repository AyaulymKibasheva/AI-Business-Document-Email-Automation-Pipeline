"""Tests for stage 11 batch document processing."""

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from app.main import discover_documents, main, process_batch


class BatchProcessingTests(unittest.TestCase):
    def test_discovers_only_supported_files_in_stable_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("B.pdf", "a.TXT", "c.docx", "ignore.png"):
                (root / name).touch()

            self.assertEqual(
                [path.name for path in discover_documents(root)],
                ["a.TXT", "B.pdf", "c.docx"],
            )

    def test_batch_continues_and_prints_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("one.pdf", "two.docx", "three.txt"):
                (root / name).touch()

            output = StringIO()
            with patch("app.main.process_document", side_effect=[0, 2, 1]), redirect_stdout(output):
                result = process_batch(root)

            self.assertEqual(result, 1)
            summary = output.getvalue()
            self.assertIn("3 received", summary)
            self.assertIn("1 processed", summary)
            self.assertIn("1 needs review", summary)
            self.assertIn("1 failed", summary)

    def test_unexpected_error_does_not_stop_following_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.txt").touch()
            (root / "two.txt").touch()

            with patch(
                "app.main.process_document", side_effect=[RuntimeError("boom"), 0]
            ) as processor, redirect_stdout(StringIO()):
                result = process_batch(root)

            self.assertEqual(result, 1)
            self.assertEqual(processor.call_count, 2)

    def test_main_routes_a_directory_to_batch_processing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch("app.main.process_batch", return_value=0) as batch:
                self.assertEqual(main([directory]), 0)
                batch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
