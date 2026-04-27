import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import create_app
from app.admin.auth import ADMIN_SESSION_KEY
from app.models import Consignment, db


class AdminSaveGeocodeFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv("DATABASE_URL"):
            raise unittest.SkipTest("DATABASE_URL is required for integration tests")

        cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def _authenticate_admin_session(self):
        with self.client.session_transaction() as session_data:
            session_data[ADMIN_SESSION_KEY] = True

    def test_save_allows_unresolved_drop_pincode_with_fallback_eta(self):
        self._authenticate_admin_session()
        consignment_number = f"HOME{uuid4().hex[:8].upper()}"

        payload = {
            "rows": [
                {
                    "consignment_number": consignment_number,
                    "status": "In Transit",
                    "pickup_pincode": "110017",
                    "drop_pincode": "222221",
                }
            ]
        }

        with patch("app.admin.consignment_controller.geocode_indian_pincode_with_retry") as geocode_mock, patch(
            "app.admin.consignment_controller.calculate_eta_breakdown_with_retry"
        ) as eta_mock:
            geocode_mock.side_effect = [
                {"lat": 28.5245, "lng": 77.2066, "source": "test"},
                None,
            ]
            eta_mock.return_value = None

            response = self.client.post("/admin/consignments/save", json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])

        with self.app.app_context():
            saved = Consignment.query.filter_by(consignment_number=consignment_number).first()
            self.assertIsNotNone(saved)
            self.assertEqual(saved.drop_pincode, "222221")

            db.session.delete(saved)
            db.session.commit()

    def test_save_deletes_rows_sent_in_deleted_ids(self):
        self._authenticate_admin_session()

        delete_number = f"DEL{uuid4().hex[:8].upper()}"
        keep_number = f"KEEP{uuid4().hex[:8].upper()}"

        with self.app.app_context():
            to_delete = Consignment(
                consignment_number=delete_number,
                status="In Transit",
                pickup_pincode="110017",
                drop_pincode="400001",
                eta="2 days",
            )
            to_keep = Consignment(
                consignment_number=keep_number,
                status="Pickup Scheduled",
                pickup_pincode="560001",
                drop_pincode="500001",
                eta="3 days",
            )
            db.session.add(to_delete)
            db.session.add(to_keep)
            db.session.commit()

            delete_id = to_delete.id
            keep_id = to_keep.id

        payload = {
            "rows": [
                {
                    "id": keep_id,
                    "consignment_number": keep_number,
                    "status": "In Transit",
                    "pickup_pincode": "560001",
                    "drop_pincode": "500001",
                }
            ],
            "deleted_ids": [delete_id],
        }

        with patch("app.admin.consignment_controller.geocode_indian_pincode_with_retry") as geocode_mock, patch(
            "app.admin.consignment_controller.calculate_eta_breakdown_with_retry"
        ) as eta_mock:
            geocode_mock.side_effect = [
                {"lat": 12.9716, "lng": 77.5946, "source": "test"},
                {"lat": 17.3850, "lng": 78.4867, "source": "test"},
            ]
            eta_mock.return_value = {
                "eta": "2 days",
                "duration_seconds": 172800,
                "duration_hours": 48.0,
                "distance_km": 570.0,
                "calculated_at": "2026-01-01 00:00",
                "route_source": "test",
                "formula": "mocked",
            }

            response = self.client.post("/admin/consignments/save", json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body.get("deleted_count"), 1)

        with self.app.app_context():
            deleted_row = Consignment.query.filter_by(id=delete_id).first()
            kept_row = Consignment.query.filter_by(id=keep_id).first()

            self.assertIsNone(deleted_row)
            self.assertIsNotNone(kept_row)
            self.assertEqual(kept_row.status, "In Transit")

            if kept_row is not None:
                db.session.delete(kept_row)
                db.session.commit()


if __name__ == "__main__":
    unittest.main()
