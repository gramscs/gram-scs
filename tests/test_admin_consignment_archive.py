import os
import unittest
from unittest.mock import patch, MagicMock

from app import create_app


class AdminConsignmentArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SECRET_KEY", "test-secret-key")
        os.environ.setdefault("ADMIN_USERNAME", "admin")
        os.environ.setdefault(
            "ADMIN_PASSWORD_HASH",
            "scrypt:32768:8:1$yFUNQ6eCe1ScMEcQ$d94441786edd350236b9340455e3302df2cbb8cf12ba94311abf8d2f1c52b75a20efc1c7a7a8ffaa0357c3b9e0f246dea70c4ea368f0346072f03f55325f913b",
        )

        with patch("app._require_database_uri", return_value="postgresql://user:pass@localhost/testdb"), patch(
            "app._should_auto_create_tables", return_value=False
        ):
            cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def test_archive_delivered_requires_cutoff_date(self):
        with patch("app.admin.auth.is_admin_authenticated", return_value=True):
            response = self.client.post(
                "/admin/consignments/archive",
                json={}
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Please provide a cutoff date", response.data)

    def test_archive_delivered_deletes_old_delivered_rows(self):
        delivered_old = MagicMock()
        delivered_old.status = "Delivered"
        delivered_old.drop_date = "2026-05-01"
        delivered_old.pod_image = "pod123.png"

        delivered_new = MagicMock()
        delivered_new.status = "Delivered"
        delivered_new.drop_date = "2026-09-01"
        delivered_new.pod_image = "pod456.png"

        in_progress = MagicMock()
        in_progress.status = "In Transit"
        in_progress.drop_date = "2026-01-01"
        in_progress.pod_image = None

        fake_query = MagicMock()
        fake_query.filter.return_value = fake_query
        # The status filter will already narrow results to only delivered consignments.
        fake_query.all.return_value = [delivered_old, delivered_new]

        with self.app.app_context():
            with patch("app.admin.auth.is_admin_authenticated", return_value=True), patch(
                "app.admin.consignment_controller.Consignment.query", fake_query
            ), patch("app.admin.consignment_controller.db") as fake_db, patch(
                "app.admin.consignment_controller._delete_pod_file"
            ) as delete_pod_file:
                fake_db.session.delete.return_value = None
                fake_db.session.commit.return_value = None
                response = self.client.post(
                    "/admin/consignments/archive",
                    json={"before_date": "2026-06-01"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json.get("success"), True)
        self.assertEqual(response.json.get("archived_count"), 1)
        delete_pod_file.assert_called_once_with("pod123.png")
        fake_db.session.delete.assert_called_once_with(delivered_old)
        fake_db.session.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
