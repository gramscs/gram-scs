import os
import unittest


# Configure required environment variables before importing app modules.
os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/gramscs"
os.environ["MASTER_DATABASE_URL"] = "postgresql://user:pass@localhost:5432/gramscs_master"
os.environ["SECRET_KEY"] = "test-secret-key-for-admin-session-auth"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD_HASH"] = "scrypt:32768:8:1$yFUNQ6eCe1ScMEcQ$d94441786edd350236b9340455e3302df2cbb8cf12ba94311abf8d2f1c52b75a20efc1c7a7a8ffaa0357c3b9e0f246dea70c4ea368f0346072f03f55325f913b"
os.environ["AUTO_CREATE_TABLES"] = "false"

from app import create_app
from app.admin.auth import ADMIN_SESSION_KEY


class AdminSessionAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

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


if __name__ == "__main__":
    unittest.main()
