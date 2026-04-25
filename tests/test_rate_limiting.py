import os
import unittest


os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/gramscs"
os.environ["MASTER_DATABASE_URL"] = "postgresql://user:pass@localhost:5432/gramscs_master"
os.environ["SECRET_KEY"] = "test-secret-key-for-rate-limiting"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD_HASH"] = "scrypt:32768:8:1$yFUNQ6eCe1ScMEcQ$d94441786edd350236b9340455e3302df2cbb8cf12ba94311abf8d2f1c52b75a20efc1c7a7a8ffaa0357c3b9e0f246dea70c4ea368f0346072f03f55325f913b"
os.environ["AUTO_CREATE_TABLES"] = "false"
os.environ["RATELIMIT_STORAGE_URI"] = "memory://"

from app import create_app


class RateLimitingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True)

    def test_admin_login_get_is_not_rate_limited(self):
        client = self.app.test_client()

        response = client.get("/admin/login", environ_overrides={"REMOTE_ADDR": "10.10.0.1"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login", response.data)

    def test_admin_login_post_is_rate_limited_after_five_requests(self):
        client = self.app.test_client()

        for attempt in range(5):
            response = client.post(
                "/admin/login",
                data={"username": "admin", "password": f"wrong-{attempt}"},
                environ_overrides={"REMOTE_ADDR": "10.10.0.2"},
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Invalid username or password.", response.data)

        limited_response = client.post(
            "/admin/login",
            data={"username": "admin", "password": "wrong-5"},
            environ_overrides={"REMOTE_ADDR": "10.10.0.2"},
            follow_redirects=False,
        )

        self.assertEqual(limited_response.status_code, 429)
        self.assertEqual(limited_response.mimetype, "text/plain")
        self.assertIn(b"Too many requests. Please try again later.", limited_response.data)


if __name__ == "__main__":
    unittest.main()