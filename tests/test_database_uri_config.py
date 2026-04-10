import os
import unittest

from app import _require_database_uri, _resolve_master_database_uri


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


if __name__ == "__main__":
    unittest.main()