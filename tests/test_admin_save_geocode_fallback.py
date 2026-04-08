import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import create_app
from app.models import Consignment, db


class AdminSaveGeocodeFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv("DATABASE_URL"):
            raise unittest.SkipTest("DATABASE_URL is required for integration tests")

        cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def test_save_allows_unresolved_drop_pincode_with_fallback_eta(self):
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

        with patch("app.admin.routes.geocode_indian_pincode_with_retry") as geocode_mock, patch(
            "app.admin.routes.calculate_eta_breakdown_with_retry"
        ) as eta_mock:
            geocode_mock.side_effect = [
                {"lat": 28.5245, "lng": 77.2066, "source": "test"},
                None,
            ]
            eta_mock.return_value = None

            response = self.client.post("/xk7m2p/save", json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])

        with self.app.app_context():
            saved = Consignment.query.filter_by(consignment_number=consignment_number).first()
            self.assertIsNotNone(saved)
            self.assertEqual(saved.drop_pincode, "222221")

            db.session.delete(saved)
            db.session.commit()


if __name__ == "__main__":
    unittest.main()