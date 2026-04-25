import os
import unittest

from app import _require_database_uri, _resolve_master_database_uri, _should_auto_create_tables


class DatabaseUriConfigTests(unittest.TestCase):
    def setUp(self):
        self._old_database_url = os.environ.get("DATABASE_URL")
        self._old_master_database_url = os.environ.get("MASTER_DATABASE_URL")

    def tearDown(self):
        if self._old_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = self._old_database_url

        if self._old_master_database_url is None:
            os.environ.pop("MASTER_DATABASE_URL", None)
        else:
            os.environ["MASTER_DATABASE_URL"] = self._old_master_database_url

    def test_require_database_uri_converts_postgres_scheme(self):
        os.environ["DATABASE_URL"] = "postgres://user:pass@localhost:5432/appdb"
        result = _require_database_uri()
        self.assertEqual(result, "postgresql://user:pass@localhost:5432/appdb")

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

    def test_resolve_master_database_uri_adds_sslmode_for_supabase_pooler(self):
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/gramscs"
        os.environ["MASTER_DATABASE_URL"] = (
            "postgresql://user:pass@aws-1-ap-south-1.pooler.supabase.com:5432/gramscs_master"
        )
        result = _resolve_master_database_uri()
        self.assertEqual(
            result,
            "postgresql://user:pass@aws-1-ap-south-1.pooler.supabase.com:5432/gramscs_master?sslmode=require",
        )

    def test_should_auto_create_tables_is_disabled_in_production(self):
        old_flask_env = os.environ.get("FLASK_ENV")
        old_auto_create_tables = os.environ.get("AUTO_CREATE_TABLES")
        try:
            os.environ["FLASK_ENV"] = "production"
            os.environ["AUTO_CREATE_TABLES"] = "true"

            self.assertFalse(_should_auto_create_tables())
        finally:
            if old_flask_env is None:
                os.environ.pop("FLASK_ENV", None)
            else:
                os.environ["FLASK_ENV"] = old_flask_env

            if old_auto_create_tables is None:
                os.environ.pop("AUTO_CREATE_TABLES", None)
            else:
                os.environ["AUTO_CREATE_TABLES"] = old_auto_create_tables


if __name__ == "__main__":
    unittest.main()