import unittest
from io import BytesIO
from openpyxl import Workbook

from app import create_app, db
from app.eta_master.models import EtaMasterRecord


class EtaMasterTypeCastingTests(unittest.TestCase):
    """Test explicit type casting and validation for each field."""

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        with self.app.app_context():
            # Clear any existing records before each test
            db.session.query(EtaMasterRecord).delete()
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            # Clear records after each test
            db.session.query(EtaMasterRecord).delete()
            db.session.commit()

    def _create_test_excel(self, **kwargs):
        """Create a test Excel file with specific values."""
        wb = Workbook()
        ws = wb.active

        headers = [
            'SNO',
            'PIN CODE',
            'PICK UP STATION',
            'STATE/UT',
            'CITY',
            'PICK UP LOCATION',
            'DELIVERY LOCATION',
            'TAT IN DAYS',
            'ZONE',
        ]
        ws.append(headers)

        # Default row
        defaults = {
            'sno': 1,
            'pin_code': '560001',
            'pickup_station': 'Bengaluru Hub',
            'state_ut': 'Karnataka',
            'city': 'Bangalore',
            'pickup_location': 'Bengaluru Station',
            'delivery_location': 'Whitefield Zone',
            'tat_in_days': 1.5,
            'zone': 'South',
        }

        # Override with kwargs
        row_data = {**defaults, **kwargs}

        ws.append([
            row_data['sno'],
            row_data['pin_code'],
            row_data['pickup_station'],
            row_data['state_ut'],
            row_data['city'],
            row_data['pickup_location'],
            row_data['delivery_location'],
            row_data['tat_in_days'],
            row_data['zone'],
        ])

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    def test_sno_cast_to_integer(self):
        """Test that SNO is cast to Integer."""
        excel_file = self._create_test_excel(sno=42)

        self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data',
        )

        with self.app.app_context():
            record = db.session.query(EtaMasterRecord).first()
            self.assertEqual(record.sno, 42)
            self.assertIsInstance(record.sno, int)

    def test_sno_cast_from_float_excel_value(self):
        """Test that SNO handles Excel's float representation (e.g., 1.0 becomes 1)."""
        excel_file = self._create_test_excel(sno=5.0)

        self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data',
        )

        with self.app.app_context():
            record = db.session.query(EtaMasterRecord).first()
            self.assertEqual(record.sno, 5)
            self.assertIsInstance(record.sno, int)

    def test_sno_optional_empty_string(self):
        """Test that empty SNO is allowed (optional field)."""
        excel_file = self._create_test_excel(sno='')

        response = self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data',
        )

        # Should succeed
        self.assertIn(b'Inserted 1', response.data)

        with self.app.app_context():
            record = db.session.query(EtaMasterRecord).first()
            self.assertIsNone(record.sno)

    def test_pincode_cast_to_string_6_digits(self):
        """Test that PIN CODE is cast to String exactly 6 digits."""
        excel_file = self._create_test_excel(pin_code='110001')

        self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data',
        )

        with self.app.app_context():
            record = db.session.query(EtaMasterRecord).first()
            self.assertEqual(record.pin_code, '110001')
            self.assertIsInstance(record.pin_code, str)
            self.assertEqual(len(record.pin_code), 6)

    def test_pincode_rejects_invalid(self):
        """Test that invalid PIN CODE is rejected."""
        excel_file = self._create_test_excel(pin_code='invalid')

        response = self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data',
        )

        # Should have errors (0 inserted)
        self.assertIn(b'errors 1', response.data)

    def test_text_fields_cast_to_string_with_max_length(self):
        """Test that text fields are cast to String and respect max lengths."""
        excel_file = self._create_test_excel(
            pickup_station='A' * 300,  # > 255 chars
        )

        response = self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data',
        )

        # Should have errors (0 inserted)
        self.assertIn(b'errors 1', response.data)

    def test_text_fields_trimmed(self):
        """Test that text fields are trimmed of whitespace."""
        excel_file = self._create_test_excel(
            pickup_station='  Bengaluru Hub  ',
            state_ut='  Karnataka  ',
            city='  Bangalore  ',
        )

        self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data',
        )

        with self.app.app_context():
            record = db.session.query(EtaMasterRecord).first()
            self.assertEqual(record.pickup_station, 'Bengaluru Hub')
            self.assertEqual(record.state_ut, 'Karnataka')
            self.assertEqual(record.city, 'Bangalore')

    def test_tat_in_days_cast_to_float(self):
        """Test that TAT IN DAYS is cast to Float."""
        excel_file = self._create_test_excel(tat_in_days=2.5)

        self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data',
        )

        with self.app.app_context():
            record = db.session.query(EtaMasterRecord).first()
            self.assertEqual(record.tat_in_days, 2.5)
            self.assertIsInstance(record.tat_in_days, float)

    def test_tat_in_days_cast_from_integer(self):
        """Test that TAT IN DAYS can accept integer values (cast to float)."""
        excel_file = self._create_test_excel(tat_in_days=3)

        self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data',
        )

        with self.app.app_context():
            record = db.session.query(EtaMasterRecord).first()
            self.assertEqual(record.tat_in_days, 3.0)
            self.assertIsInstance(record.tat_in_days, float)

    def test_tat_in_days_rejects_negative(self):
        """Test that negative TAT IN DAYS is rejected."""
        excel_file = self._create_test_excel(tat_in_days=-1.5)

        response = self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data',
        )

        # Should have errors (0 inserted)
        self.assertIn(b'errors 1', response.data)

    def test_tat_in_days_rejects_non_numeric(self):
        """Test that non-numeric TAT IN DAYS is rejected."""
        excel_file = self._create_test_excel(tat_in_days='abc')

        response = self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data',
        )

        # Should have errors (0 inserted)
        self.assertIn(b'errors 1', response.data)

    def test_all_fields_cast_correctly_in_single_row(self):
        """Test that all fields are correctly cast in a single complete row."""
        excel_file = self._create_test_excel(
            sno=99,
            pin_code='400001',
            pickup_station='Mumbai Hub',
            state_ut='Maharashtra',
            city='Mumbai',
            pickup_location='Mumbai Port',
            delivery_location='Borivali Zone',
            tat_in_days=2.0,
            zone='West',
        )

        self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data',
        )

        with self.app.app_context():
            record = db.session.query(EtaMasterRecord).first()

            # Verify types and values
            self.assertEqual(record.sno, 99)
            self.assertIsInstance(record.sno, int)

            self.assertEqual(record.pin_code, '400001')
            self.assertIsInstance(record.pin_code, str)

            self.assertEqual(record.pickup_station, 'Mumbai Hub')
            self.assertIsInstance(record.pickup_station, str)

            self.assertEqual(record.state_ut, 'Maharashtra')
            self.assertIsInstance(record.state_ut, str)

            self.assertEqual(record.city, 'Mumbai')
            self.assertIsInstance(record.city, str)

            self.assertEqual(record.pickup_location, 'Mumbai Port')
            self.assertIsInstance(record.pickup_location, str)

            self.assertEqual(record.delivery_location, 'Borivali Zone')
            self.assertIsInstance(record.delivery_location, str)

            self.assertEqual(record.tat_in_days, 2.0)
            self.assertIsInstance(record.tat_in_days, float)

            self.assertEqual(record.zone, 'West')
            self.assertIsInstance(record.zone, str)


if __name__ == '__main__':
    unittest.main()
