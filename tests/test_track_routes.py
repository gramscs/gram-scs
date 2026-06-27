import unittest
import os
from unittest.mock import MagicMock, patch

from app import create_app


class FakeConsignment:
    def __init__(self):
        self.consignment_number = "ABC123"
        self.status = "In Transit"
        self.pickup_pincode = "110017"
        self.drop_pincode = "110018"
        self.eta = None
        self.eta_debug_json = None
        self.pickup_address = "Pickup address"
        self.pickup_tag = "Origin"
        self.pickup_date = "2026-04-01"
        self.drop_address = "Drop address"
        self.drop_tag = "Destination"
        self.drop_date = "2026-04-05"
        self.pod_image = None


class TrackRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv("DATABASE_URL"):
            raise unittest.SkipTest("DATABASE_URL is required for tests")
        cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def test_track_page_loads(self):
        response = self.client.get("/track")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Track Your Shipment", response.data)
        self.assertIn(b"Enter Consignment Number", response.data)

    def test_invalid_consignment_logs_and_returns_message(self):
        with patch("app.frontend.routes.track.routes.logger") as mock_logger:
            response = self.client.post("/track", data={"consignment_number": "bad!!"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid consignment number format.", response.data)
        mock_logger.warning.assert_any_call("Rejected invalid consignment number: %s", "BAD!!")

    def test_missing_consignment_logs_lookup_miss(self):
        fake_query = MagicMock()
        fake_query.filter_by.return_value.first.return_value = None

        fake_model = MagicMock()
        fake_model.query = fake_query

        with patch("app.frontend.routes.track.routes.TrackConsignment", fake_model), patch("app.frontend.routes.track.routes.logger") as mock_logger:
            response = self.client.post("/track", data={"consignment_number": "HOME123"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Consignment not found. Please check the number and try again.", response.data)
        mock_logger.info.assert_any_call("Shipment not found for consignment %s", "HOME123")

    def test_found_consignment_uses_saved_eta_without_refreshing_coordinates(self):
        record = FakeConsignment()
        record.eta = "2026-04-05 12:00"
        fake_query = MagicMock()
        fake_query.filter_by.return_value.first.return_value = record

        fake_model = MagicMock()
        fake_model.query = fake_query

        with (
            patch("app.frontend.routes.track.routes.TrackConsignment", fake_model),
            patch("app.frontend.routes.track.routes.db.session.commit") as mock_commit,
            patch("app.frontend.routes.track.routes.logger") as mock_logger,
        ):
            response = self.client.post("/track", data={"consignment_number": "ABC123"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'value="ABC123"', response.data)
        self.assertEqual(record.eta, "2026-04-05 12:00")
        mock_commit.assert_not_called()
        mock_logger.info.assert_any_call("Shipment found for consignment %s", "ABC123")

    def test_track_page_does_not_render_map_markup(self):
        response = self.client.get("/track")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'id="map"', response.data)
        self.assertIn(b"track-widget.js", response.data)

    def test_track_lookup_api_returns_current_project_data_shape(self):
        record = FakeConsignment()
        fake_query = MagicMock()
        fake_query.filter_by.return_value.first.return_value = record

        fake_model = MagicMock()
        fake_model.query = fake_query

        with patch("app.frontend.routes.track.routes.TrackConsignment", fake_model):
            response = self.client.get("/api/track/abc123")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["consignment_number"], "ABC123")
        self.assertEqual(payload["data"]["pickup_address"], "Pickup address")
        self.assertFalse(payload["data"]["pod_image"])

    def test_track_lookup_api_returns_404_for_missing_consignment(self):
        fake_query = MagicMock()
        fake_query.filter_by.return_value.first.return_value = None

        fake_model = MagicMock()
        fake_model.query = fake_query

        with patch("app.frontend.routes.track.routes.TrackConsignment", fake_model):
            response = self.client.get("/api/track/MISSING1")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Consignment not found", response.get_json()["message"])


if __name__ == "__main__":
    unittest.main()
