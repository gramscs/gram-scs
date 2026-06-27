import importlib
import os
import unittest

import app.admin.auth as admin_auth


class AdminAuthConfigTests(unittest.TestCase):
    def setUp(self):
        self._old_flask_env = os.environ.get("FLASK_ENV")
        self._old_admin_username = os.environ.get("ADMIN_USERNAME")
        self._old_admin_password_hash = os.environ.get("ADMIN_PASSWORD_HASH")
        self._old_admin_password = os.environ.get("ADMIN_PASSWORD")

    def tearDown(self):
        if self._old_flask_env is None:
            os.environ.pop("FLASK_ENV", None)
        else:
            os.environ["FLASK_ENV"] = self._old_flask_env

        if self._old_admin_username is None:
            os.environ.pop("ADMIN_USERNAME", None)
        else:
            os.environ["ADMIN_USERNAME"] = self._old_admin_username

        if self._old_admin_password_hash is None:
            os.environ.pop("ADMIN_PASSWORD_HASH", None)
        else:
            os.environ["ADMIN_PASSWORD_HASH"] = self._old_admin_password_hash

        if self._old_admin_password is None:
            os.environ.pop("ADMIN_PASSWORD", None)
        else:
            os.environ["ADMIN_PASSWORD"] = self._old_admin_password

        importlib.reload(admin_auth)

    def test_uses_local_default_password_outside_production(self):
        os.environ.pop("FLASK_ENV", None)
        os.environ.pop("ADMIN_PASSWORD_HASH", None)
        os.environ.pop("ADMIN_PASSWORD", None)
        importlib.reload(admin_auth)

        self.assertTrue(admin_auth.check_admin_credentials("admin", "admin-pass"))
        self.assertFalse(admin_auth.check_admin_credentials("admin", "wrong-password"))

    def test_accepts_admin_e2e_password_alias_outside_production(self):
        os.environ.pop("FLASK_ENV", None)
        os.environ.pop("ADMIN_PASSWORD_HASH", None)
        os.environ.pop("ADMIN_PASSWORD", None)
        os.environ["ADMIN_E2E_PASSWORD"] = "e2e-secret"
        importlib.reload(admin_auth)

        self.assertTrue(admin_auth.check_admin_credentials("admin", "e2e-secret"))
        self.assertFalse(admin_auth.check_admin_credentials("admin", "wrong-password"))

    def test_requires_admin_password_hash_in_production(self):
        os.environ["FLASK_ENV"] = "production"
        os.environ.pop("ADMIN_PASSWORD_HASH", None)
        os.environ.pop("ADMIN_PASSWORD", None)
        os.environ.pop("ADMIN_E2E_PASSWORD", None)

        with self.assertRaises(RuntimeError):
            importlib.reload(admin_auth)


if __name__ == "__main__":
    unittest.main()