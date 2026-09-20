"""Static validation for the stage 18 container configuration."""

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]


class DockerConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        cls.compose = yaml.safe_load(cls.compose_text)
        cls.dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    def test_compose_contains_required_services(self) -> None:
        self.assertEqual(
            set(self.compose["services"]),
            {"api", "mysql", "n8n", "dashboard"},
        )

    def test_api_waits_for_healthy_mysql(self) -> None:
        dependency = self.compose["services"]["api"]["depends_on"]["mysql"]
        self.assertEqual(dependency["condition"], "service_healthy")
        self.assertIn("healthcheck", self.compose["services"]["mysql"])

    def test_n8n_waits_for_healthy_api(self) -> None:
        dependency = self.compose["services"]["n8n"]["depends_on"]["api"]
        self.assertEqual(dependency["condition"], "service_healthy")
        self.assertIn("HEALTHCHECK", self.dockerfile)

    def test_dashboard_has_streamlit_healthcheck(self) -> None:
        healthcheck = self.compose["services"]["dashboard"]["healthcheck"]
        self.assertIn("8501/_stcore/health", " ".join(healthcheck["test"]))

    def test_persistent_named_volumes_are_defined(self) -> None:
        self.assertTrue(
            {"mysql-data", "app-data", "app-logs", "n8n-data"}.issubset(
                self.compose["volumes"]
            )
        )

    def test_no_real_secrets_are_committed(self) -> None:
        self.assertNotIn("123456", self.compose_text)
        self.assertNotIn("IMAP_PASSWORD=", self.compose_text)

    def test_container_runs_as_non_root_user(self) -> None:
        self.assertIn("USER app", self.dockerfile)


if __name__ == "__main__":
    unittest.main()
