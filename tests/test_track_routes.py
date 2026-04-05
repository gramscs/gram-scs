import unittest
from unittest.mock import MagicMock, patch

from app import create_app


class FakeConsignment:
    def __init__(self):
        self.consignment_number = "ABC123"
        self.status = "In Transit"
        self.pickup_pincode = "110017"
        self.drop_pincode = "110018"
        self.pickup_lat = None
        self.pickup_lng = None
        self.drop_lat = None
        self.drop_lng = None
        self.eta = None
        self.eta_debug_json = None


class TrackRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def test_track_page_loads(self):
        response = self.client.get("/track")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Track Your Shipment", response.data)
        self.assertIn(b"Enter Consignment Number", response.data)

    def test_invalid_consignment_logs_and_returns_message(self):
        with patch("app.track.routes.logger") as mock_logger:
            response = self.client.post("/track", data={"consignment_number": "bad!!"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid consignment number format.", response.data)
        mock_logger.warning.assert_any_call("Rejected invalid consignment number: %s", "BAD!!")

    def test_missing_consignment_logs_lookup_miss(self):
        fake_query = MagicMock()
        fake_query.filter_by.return_value.first.return_value = None

        fake_model = MagicMock()
        fake_model.query = fake_query

        with patch("app.track.routes.TrackConsignment", fake_model), patch("app.track.routes.logger") as mock_logger:
            response = self.client.post("/track", data={"consignment_number": "HOME123"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Consignment not found. Please check the number and try again.", response.data)
        mock_logger.info.assert_any_call("Shipment not found for consignment %s", "HOME123")

    def test_found_consignment_refreshes_eta(self):
        record = FakeConsignment()
        fake_query = MagicMock()
        fake_query.filter_by.return_value.first.return_value = record

        fake_model = MagicMock()
        fake_model.query = fake_query

        geocode_values = [
            {"lat": 28.6139, "lng": 77.209, "source": "mock"},
            {"lat": 19.076, "lng": 72.8777, "source": "mock"},
        ]

        def geocode_side_effect(*args, **kwargs):
            return geocode_values.pop(0)

        eta_breakdown = {
            "eta": "2026-04-05 12:00",
            "duration_seconds": 3600,
            "duration_hours": 1.0,
            "osrm_base_hours": 1.0,
            "truck_multiplier": 1.7,
            "truck_buffer_hours": 6.0,
            "adjusted_truck_hours": 7.0,
            "distance_km": 10.0,
            "calculated_at": "2026-04-05 05:00",
            "route_source": "mock",
            "formula": "Adjusted_Truck_ETA = OSRM_base_time * 1.7 + 6",
        }

        with (
            patch("app.track.routes.TrackConsignment", fake_model),
            patch("app.track.routes.geocode_indian_pincode_with_retry", side_effect=geocode_side_effect),
            patch("app.track.routes.calculate_eta_breakdown_with_retry", return_value=eta_breakdown),
            patch("app.track.routes.db.session.commit") as mock_commit,
            patch("app.track.routes.logger") as mock_logger,
        ):
            response = self.client.post("/track", data={"consignment_number": "ABC123"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"2026-04-05 12:00", response.data)
        self.assertEqual(record.eta, "2026-04-05 12:00")
        self.assertEqual(record.pickup_lat, 28.6139)
        self.assertEqual(record.drop_lng, 72.8777)
        mock_commit.assert_called_once()
        mock_logger.info.assert_any_call("Shipment found for consignment %s", "ABC123")


if __name__ == "__main__":
    unittest.main()
