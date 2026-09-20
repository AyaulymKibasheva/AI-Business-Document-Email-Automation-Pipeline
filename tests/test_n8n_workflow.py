"""Structural tests for the importable stage 15 n8n workflow."""

import json
import unittest
from pathlib import Path


WORKFLOW_PATH = (
    Path(__file__).parents[1] / "n8n" / "workflows" / "email-document-pipeline.json"
)


class N8nWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
        cls.nodes = {node["name"]: node for node in cls.workflow["nodes"]}

    def test_workflow_is_safe_to_import_inactive(self) -> None:
        self.assertFalse(self.workflow["active"])
        self.assertNotIn("credentials", WORKFLOW_PATH.read_text(encoding="utf-8"))

    def test_contains_email_filter_api_and_review_nodes(self) -> None:
        self.assertEqual(
            self.nodes["Gmail IMAP Trigger"]["type"],
            "n8n-nodes-base.emailReadImap",
        )
        self.assertEqual(
            self.nodes["Keep Supported Attachments"]["type"],
            "n8n-nodes-base.code",
        )
        self.assertEqual(
            self.nodes["Send Document to Python API"]["type"],
            "n8n-nodes-base.httpRequest",
        )
        self.assertIn("Needs Review?", self.nodes)

    def test_http_request_uses_multipart_file_upload(self) -> None:
        parameters = self.nodes["Send Document to Python API"]["parameters"]
        self.assertEqual(parameters["method"], "POST")
        self.assertEqual(parameters["contentType"], "multipart-form-data")
        body = parameters["bodyParameters"]["parameters"]
        self.assertTrue(
            any(
                item.get("parameterType") == "formBinaryData"
                and item.get("name") == "file"
                for item in body
            )
        )

    def test_every_connection_targets_an_existing_node(self) -> None:
        for source, groups in self.workflow["connections"].items():
            self.assertIn(source, self.nodes)
            for branch in groups["main"]:
                for connection in branch:
                    self.assertIn(connection["node"], self.nodes)


if __name__ == "__main__":
    unittest.main()
