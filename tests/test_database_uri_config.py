import os
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import _require_database_uri, _should_auto_create_tables
import app.config as app_config


class DatabaseUriConfigTests(unittest.TestCase):
    def setUp(self):
        self._old_database_url = os.environ.get("DATABASE_URL")
        self._old_flask_env = os.environ.get("FLASK_ENV")

    def tearDown(self):
        if self._old_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = self._old_database_url

        if self._old_flask_env is None:
            os.environ.pop("FLASK_ENV", None)
        else:
            os.environ["FLASK_ENV"] = self._old_flask_env

    def test_require_database_uri_uses_local_sqlite_fallback_when_unset(self):
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("FLASK_ENV", None)

        result = _require_database_uri()

        self.assertTrue(result.startswith("sqlite:///"))
        self.assertIn("instance/dev.db", result)

    def test_require_database_uri_converts_postgres_scheme(self):
        os.environ["DATABASE_URL"] = "postgres://user:pass@localhost:5432/appdb"
        result = _require_database_uri()
        self.assertEqual(result, "postgresql://user:pass@localhost:5432/appdb")

    def test_sqlite_database_directory_is_created_before_app_startup(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sqlite_path = Path(tmp_dir) / "nested" / "db" / "app.db"
            sqlite_url = f"sqlite:///{sqlite_path}"

            from app import _ensure_sqlite_parent_directory

            _ensure_sqlite_parent_directory(sqlite_url)

            self.assertTrue(sqlite_path.parent.exists())

    def test_sqlite_database_uri_is_normalized_to_absolute_path(self):
        from app import _normalize_sqlite_database_uri

        normalized = _normalize_sqlite_database_uri("sqlite:///./instance/dev.db")

        self.assertTrue(normalized.startswith("sqlite:///"))
        self.assertIn("instance/dev.db", normalized)
        self.assertNotEqual(normalized, "sqlite:///./instance/dev.db")

    def test_require_database_uri_adds_sslmode_for_supabase_pooler(self):
        os.environ["DATABASE_URL"] = (
            "postgresql://user:pass@aws-1-ap-south-1.pooler.supabase.com:5432/gramscs"
        )
        result = _require_database_uri()
        self.assertEqual(
            result,
            "postgresql://user:pass@aws-1-ap-south-1.pooler.supabase.com:5432/gramscs?sslmode=require",
        )

    def test_require_database_uri_keeps_existing_sslmode_for_supabase_pooler(self):
        os.environ["DATABASE_URL"] = (
            "postgresql://user:pass@aws-1-ap-south-1.pooler.supabase.com:5432/gramscs?sslmode=require"
        )
        result = _require_database_uri()
        self.assertEqual(
            result,
            "postgresql://user:pass@aws-1-ap-south-1.pooler.supabase.com:5432/gramscs?sslmode=require",
        )

    def test_should_auto_create_tables_is_disabled_in_production(self):
        old_auto_create_tables = os.environ.get("AUTO_CREATE_TABLES")
        try:
            os.environ["FLASK_ENV"] = "production"
            os.environ["AUTO_CREATE_TABLES"] = "true"

            self.assertFalse(_should_auto_create_tables())
        finally:
            if old_auto_create_tables is None:
                os.environ.pop("AUTO_CREATE_TABLES", None)
            else:
                os.environ["AUTO_CREATE_TABLES"] = old_auto_create_tables

    def test_startup_schema_repair_failure_logs_warning_instead_of_error(self):
        old_auto_create_tables = os.environ.get("AUTO_CREATE_TABLES")
        old_database_url = os.environ.get("DATABASE_URL")
        old_flask_env = os.environ.get("FLASK_ENV")
        old_secret_key = os.environ.get("SECRET_KEY")

        try:
            os.environ["FLASK_ENV"] = "production"
            os.environ["AUTO_CREATE_TABLES"] = "false"
            os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/appdb"
            os.environ["SECRET_KEY"] = "test-secret-key"
            os.environ["ADMIN_PASSWORD"] = "test-admin-password"

            with mock.patch("app.ensure_consignment_columns_async", side_effect=RuntimeError("boom")), \
                 self.assertLogs("app", level="WARNING") as captured:
                app = importlib.import_module("app")
                app.create_app()

            self.assertTrue(any("schema repair" in message.lower() for message in captured.output))
            self.assertTrue(any("warning" in message.lower() for message in captured.output))
        finally:
            if old_auto_create_tables is None:
                os.environ.pop("AUTO_CREATE_TABLES", None)
            else:
                os.environ["AUTO_CREATE_TABLES"] = old_auto_create_tables

            if old_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = old_database_url

            if old_flask_env is None:
                os.environ.pop("FLASK_ENV", None)
            else:
                os.environ["FLASK_ENV"] = old_flask_env

            if old_secret_key is None:
                os.environ.pop("SECRET_KEY", None)
            else:
                os.environ["SECRET_KEY"] = old_secret_key

    def test_resolve_secret_key_uses_local_fallback_outside_production(self):
        old_secret_key = os.environ.pop("SECRET_KEY", None)
        old_flask_env = os.environ.pop("FLASK_ENV", None)
        try:
            importlib.reload(app_config)
            self.assertEqual(app_config.SECRET_KEY, "dev-local-secret-key")
        finally:
            if old_secret_key is None:
                os.environ.pop("SECRET_KEY", None)
            else:
                os.environ["SECRET_KEY"] = old_secret_key

            if old_flask_env is None:
                os.environ.pop("FLASK_ENV", None)
            else:
                os.environ["FLASK_ENV"] = old_flask_env

            importlib.reload(app_config)


if __name__ == "__main__":
    unittest.main()