import os
import unittest


os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-security-headers")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "scrypt:32768:8:1$yFUNQ6eCe1ScMEcQ$d94441786edd350236b9340455e3302df2cbb8cf12ba94311abf8d2f1c52b75a20efc1c7a7a8ffaa0357c3b9e0f246dea70c4ea368f0346072f03f55325f913b")
os.environ.setdefault("AUTO_CREATE_TABLES", "false")
os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")

from app import create_app


class SecurityHeadersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def test_health_route_includes_security_headers(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(
            response.headers.get("Referrer-Policy"),
            "strict-origin-when-cross-origin",
        )
        self.assertIn("Content-Security-Policy", response.headers)
        self.assertIn("frame-ancestors 'self'", response.headers.get("Content-Security-Policy", ""))


if __name__ == "__main__":
    unittest.main()