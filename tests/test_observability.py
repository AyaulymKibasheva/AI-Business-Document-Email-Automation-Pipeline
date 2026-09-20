"""Tests for stage 17 logs and retry behavior."""

import logging
import tempfile
import unittest
from pathlib import Path

from app.observability import configure_logging, retry_call


class ObservabilityTests(unittest.TestCase):
    def test_retries_until_operation_succeeds(self) -> None:
        calls = []
        delays = []

        def operation():
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError("temporary")
            return "ok"

        result = retry_call(
            operation,
            attempts=3,
            base_delay_seconds=0.5,
            sleep=delays.append,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 3)
        self.assertEqual(delays, [0.5, 1.0])

    def test_raises_final_error_after_limit(self) -> None:
        calls = []

        def operation():
            calls.append(1)
            raise ConnectionError("still unavailable")

        with self.assertRaisesRegex(ConnectionError, "still unavailable"):
            retry_call(operation, attempts=2, base_delay_seconds=0, sleep=lambda _: None)

        self.assertEqual(len(calls), 2)

    def test_writes_utf8_application_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.log"
            configure_logging(path)
            logging.getLogger("test.stage17").error("Ошибка обработки документа")
            for handler in logging.getLogger().handlers:
                handler.flush()

            self.assertIn("Ошибка обработки документа", path.read_text(encoding="utf-8"))
            root = logging.getLogger()
            for handler in list(root.handlers):
                if isinstance(handler, logging.FileHandler) and Path(
                    handler.baseFilename
                ) == path.resolve():
                    root.removeHandler(handler)
                    handler.close()


if __name__ == "__main__":
    unittest.main()
