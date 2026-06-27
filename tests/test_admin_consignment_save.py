import base64
import os
import unittest
from unittest.mock import patch


class AdminConsignmentSaveTests(unittest.TestCase):
    def setUp(self):
        self.db_path = "/tmp/gram_admin_save_test.db"
        try:
            os.remove(self.db_path)
        except FileNotFoundError:
            pass

        os.environ["FLASK_ENV"] = "development"
        os.environ["DATABASE_URL"] = f"sqlite:///{self.db_path}"
        os.environ.setdefault("SECRET_KEY", "test-secret-key")

        from app import create_app
        from app.models import db

        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()
        self.db = db

    def tearDown(self):
        with self.app.app_context():
            self.db.session.remove()
        try:
            os.remove(self.db_path)
        except FileNotFoundError:
            pass

    def _post_save(self, payload):
        with patch("app.admin.auth.is_admin_authenticated", return_value=True):
            return self.client.post("/admin/consignments/save", json=payload)

    def test_save_all_creates_consignment_with_pod_upload(self):
        pod_bytes = b"fake-pod-image-bytes"
        pod_data_url = "data:image/jpeg;base64," + base64.b64encode(pod_bytes).decode("ascii")

        response = self._post_save({
            "rows": [{
                "id": None,
                "consignment_number": "PODSAVE001",
                "status": "In Transit",
                "pickup_pincode": "110001",
                "pickup_address": "Delhi Hub",
                "pickup_tag": "DEL",
                "pickup_date": "2026-06-19",
                "drop_pincode": "400001",
                "drop_address": "Mumbai Client",
                "drop_tag": "MUM",
                "drop_date": "2026-06-21",
                "eta": "2026-06-21 10:00",
                "pod_file_name": "pod.jpg",
                "pod_file_type": "image/jpeg",
                "pod_file_data": pod_data_url,
            }],
            "deleted_ids": [],
        })

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["success"])

        from app.models import Consignment
        with self.app.app_context():
            row = Consignment.query.filter_by(consignment_number="PODSAVE001").first()
            self.assertIsNotNone(row)
            self.assertEqual(row.status, "In Transit")
            self.assertTrue(row.pod_image)
            with open(os.path.join(self.app.instance_path, "uploads", row.pod_image), "rb") as handle:
                self.assertEqual(handle.read(), pod_bytes)

    def test_save_all_updates_existing_consignment_data(self):
        from app.models import Consignment

        with self.app.app_context():
            row = Consignment(
                consignment_number="EDITME001",
                status="Pickup Scheduled",
                pickup_pincode="110001",
                drop_pincode="400001",
            )
            self.db.session.add(row)
            self.db.session.commit()
            row_id = row.id

        response = self._post_save({
            "rows": [{
                "id": row_id,
                "consignment_number": "EDITME001",
                "status": "Delivered",
                "pickup_pincode": "110017",
                "pickup_address": "Updated pickup address",
                "pickup_tag": "UPDATED-PICKUP",
                "pickup_date": "2026-06-18",
                "drop_pincode": "400099",
                "drop_address": "Updated drop address",
                "drop_tag": "UPDATED-DROP",
                "drop_date": "2026-06-19",
                "eta": "2026-06-19 16:30",
            }],
            "deleted_ids": [],
        })

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertTrue(response.get_json()["success"])

        with self.app.app_context():
            updated = self.db.session.get(Consignment, row_id)
            self.assertEqual(updated.status, "Delivered")
            self.assertEqual(updated.pickup_address, "Updated pickup address")
            self.assertEqual(updated.drop_pincode, "400099")
            self.assertEqual(updated.eta, "2026-06-19 16:30")


if __name__ == "__main__":
    unittest.main()
