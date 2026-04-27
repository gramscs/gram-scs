import os
import unittest
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


# Configure required environment variables before importing app modules.
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/gramscs")
os.environ.setdefault("MASTER_DATABASE_URL", "postgresql://user:pass@localhost:5432/gramscs_master")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-admin-session-auth")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "scrypt:32768:8:1$yFUNQ6eCe1ScMEcQ$d94441786edd350236b9340455e3302df2cbb8cf12ba94311abf8d2f1c52b75a20efc1c7a7a8ffaa0357c3b9e0f246dea70c4ea368f0346072f03f55325f913b")
os.environ.setdefault("AUTO_CREATE_TABLES", "false")

from app import create_app
from app.admin.auth import ADMIN_SESSION_KEY


class AdminSessionAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def setUp(self):
        with self.client.session_transaction() as session_data:
            session_data.clear()

    def test_login_success_with_correct_credentials(self):
        response = self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "gram@2017"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin/dashboard"))

        with self.client.session_transaction() as session_data:
            self.assertTrue(session_data.get(ADMIN_SESSION_KEY))

    def test_login_fails_with_wrong_password(self):
        response = self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "wrong-password"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid username or password.", response.data)

        with self.client.session_transaction() as session_data:
            self.assertFalse(session_data.get(ADMIN_SESSION_KEY, False))

    def test_logout_clears_admin_session(self):
        with self.client.session_transaction() as session_data:
            session_data[ADMIN_SESSION_KEY] = True

        response = self.client.get("/admin/logout", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin/login"))

        with self.client.session_transaction() as session_data:
            self.assertFalse(session_data.get(ADMIN_SESSION_KEY, False))

    def test_generate_backup_requires_admin_session(self):
        response = self.client.get("/admin/generate-backup", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin/login"))

    @patch("app.admin.routes.EtaMasterRecord")
    @patch("app.admin.routes.NewsletterSubscriber")
    @patch("app.admin.routes.Lead")
    @patch("app.admin.routes.Consignment")
    def test_generate_backup_returns_download_file(self, mock_consignment, mock_lead, mock_newsletter, mock_eta_master):
        with self.client.session_transaction() as session_data:
            session_data[ADMIN_SESSION_KEY] = True
            session_data["admin_username"] = "admin"

        mock_consignment_row = SimpleNamespace(
            __table__=SimpleNamespace(columns=[
                SimpleNamespace(name="id"),
                SimpleNamespace(name="consignment_number"),
                SimpleNamespace(name="eta_debug_json"),
            ]),
            id=1,
            consignment_number="CN001",
            eta_debug_json="debug",
        )

        mock_lead_row = SimpleNamespace(
            __table__=SimpleNamespace(columns=[
                SimpleNamespace(name="id"),
                SimpleNamespace(name="email"),
            ]),
            id=7,
            email="lead@example.com",
        )

        mock_newsletter_row = SimpleNamespace(
            __table__=SimpleNamespace(columns=[
                SimpleNamespace(name="id"),
                SimpleNamespace(name="email"),
            ]),
            id=2,
            email="sub@example.com",
        )

        mock_eta_row = SimpleNamespace(
            __table__=SimpleNamespace(columns=[
                SimpleNamespace(name="id"),
                SimpleNamespace(name="pin_code"),
            ]),
            id=3,
            pin_code="110017",
        )

        mock_consignment.id.asc.return_value = "ignored"
        mock_lead.id.asc.return_value = "ignored"
        mock_newsletter.id.asc.return_value = "ignored"
        mock_eta_master.id.asc.return_value = "ignored"

        mock_consignment.query.order_by.return_value.all.return_value = [mock_consignment_row]
        mock_lead.query.order_by.return_value.all.return_value = [mock_lead_row]
        mock_newsletter.query.order_by.return_value.all.return_value = [mock_newsletter_row]
        mock_eta_master.query.order_by.return_value.all.return_value = [mock_eta_row]

        response = self.client.get("/admin/generate-backup")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/json")
        self.assertIn("attachment;", response.headers.get("Content-Disposition", ""))
        self.assertIn("backup_", response.headers.get("Content-Disposition", ""))
        self.assertIn(".json", response.headers.get("Content-Disposition", ""))

        payload = json.loads(response.data.decode("utf-8"))
        self.assertIn("consignments", payload)
        self.assertIn("leads", payload)
        self.assertIn("newsletter_subscribers", payload)
        self.assertIn("eta_master_records", payload)
        self.assertIn("metadata", payload)
        self.assertNotIn("eta_debug_json", payload["consignments"][0])

    @patch("app.admin.routes.Consignment")
    def test_generate_backup_returns_json_error_on_failure(self, mock_consignment):
        with self.client.session_transaction() as session_data:
            session_data[ADMIN_SESSION_KEY] = True

        mock_consignment.id.asc.return_value = "ignored"
        mock_consignment.query.order_by.side_effect = Exception("boom")

        response = self.client.get(
            "/admin/generate-backup",
            headers={"Accept": "application/json"},
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.mimetype, "application/json")
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["message"], "Failed to generate backup.")


if __name__ == "__main__":
    unittest.main()
