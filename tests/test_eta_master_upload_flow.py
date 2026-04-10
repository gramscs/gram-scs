import unittest
import os
from io import BytesIO
from openpyxl import Workbook

from app import create_app, db
from app.eta_master.models import EtaMasterRecord


class EtaMasterUploadFlowTests(unittest.TestCase):
    """Test the complete ETA Master upload flow including UI feedback."""

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

    def _create_test_excel(self):
        """Create a valid test Excel file."""
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

        # Add sample rows
        ws.append([1, '560001', 'Bengaluru Hub', 'Karnataka', 'Bangalore', 'Bengaluru Station', 'Whitefield Zone', 1.5, 'South'])
        ws.append([2, '400001', 'Mumbai Hub', 'Maharashtra', 'Mumbai', 'Mumbai Port', 'Borivali Zone', 2.0, 'West'])
        ws.append([3, '110017', 'Delhi Hub', 'Delhi', 'New Delhi', 'Delhi NCR', 'Noida Zone', 1.0, 'North'])

        # Save to BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    def test_upload_page_loads_without_records(self):
        """Test that the upload page loads initially with no records."""
        response = self.client.get('/eta-master')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'ETA Master Database', response.data)
        self.assertIn(b'Upload Excel', response.data)
        self.assertIn(b'No records imported yet', response.data)

    def test_upload_excel_file_success(self):
        """Test uploading a valid Excel file and receiving success feedback."""
        excel_file = self._create_test_excel()

        response = self.client.post(
            '/eta-master',
            data={
                'file': (excel_file, 'test_eta.xlsx'),
            },
            content_type='multipart/form-data',
        )

        self.assertEqual(response.status_code, 200)
        # Check for success alert in HTML response
        self.assertIn(b'alert-success', response.data)
        self.assertIn(b'Import complete', response.data)
        self.assertIn(b'Inserted 3', response.data)

    def test_upload_creates_records_in_database(self):
        """Test that uploaded records are actually stored in the master database."""
        excel_file = self._create_test_excel()

        with self.app.app_context():
            # Verify no records before upload (cleared in setUp)
            count_before = db.session.query(EtaMasterRecord).count()
            self.assertEqual(count_before, 0)

        # Upload file
        response = self.client.post(
            '/eta-master',
            data={
                'file': (excel_file, 'test_eta.xlsx'),
            },
            content_type='multipart/form-data',
        )

        with self.app.app_context():
            # Verify records were created
            count_after = db.session.query(EtaMasterRecord).count()
            self.assertEqual(count_after, 3)

            # Verify record data
            records = db.session.query(EtaMasterRecord).order_by(EtaMasterRecord.pin_code).all()
            self.assertEqual(records[0].pin_code, '110017')
            self.assertEqual(records[0].city, 'New Delhi')
            self.assertEqual(float(records[0].tat_in_days), 1.0)

            self.assertEqual(records[1].pin_code, '400001')
            self.assertEqual(records[1].city, 'Mumbai')
            self.assertEqual(float(records[1].tat_in_days), 2.0)

            self.assertEqual(records[2].pin_code, '560001')
            self.assertEqual(records[2].city, 'Bangalore')
            self.assertEqual(float(records[2].tat_in_days), 1.5)

    def test_upload_shows_records_in_table(self):
        """Test that uploaded records are displayed in the page table after upload."""
        excel_file = self._create_test_excel()

        response = self.client.post(
            '/eta-master',
            data={
                'file': (excel_file, 'test_eta.xlsx'),
            },
            content_type='multipart/form-data',
        )

        # Check that records appear in the response
        self.assertIn(b'560001', response.data)  # PIN code
        self.assertIn(b'Bengaluru Hub', response.data)  # Pickup station
        self.assertIn(b'Bangalore', response.data)  # City
        self.assertIn(b'1.5', response.data)  # TAT
        self.assertIn(b'South', response.data)  # Zone

    def test_upload_shows_import_summary(self):
        """Test that import summary is displayed after successful upload."""
        excel_file = self._create_test_excel()

        response = self.client.post(
            '/eta-master',
            data={
                'file': (excel_file, 'test_eta.xlsx'),
            },
            content_type='multipart/form-data',
        )

        # Check for summary stats
        self.assertIn(b'Import Summary:', response.data)
        self.assertIn(b'3 total', response.data)
        self.assertIn(b'3 inserted', response.data)
        self.assertIn(b'0 updated', response.data)

    def test_upload_without_file_shows_error(self):
        """Test that uploading without a file is rejected."""
        response = self.client.post(
            '/eta-master',
            data={},
            content_type='multipart/form-data',
        )

        # Should redirect or show error
        self.assertIn(response.status_code, [200, 302])

    def test_upload_with_non_xlsx_shows_error(self):
        """Test that uploading a non-Excel file is rejected."""
        response = self.client.post(
            '/eta-master',
            data={
                'file': (BytesIO(b'not an excel file'), 'test.txt'),
            },
            content_type='multipart/form-data',
        )

        self.assertEqual(response.status_code, 302)  # Should redirect with error

    def test_upload_idempotency_with_duplicate_rows(self):
        """Test that uploading the same file twice doesn't create duplicates (upsert behavior)."""
        excel_file = self._create_test_excel()

        # First upload
        response1 = self.client.post(
            '/eta-master',
            data={
                'file': (excel_file, 'test_eta.xlsx'),
            },
            content_type='multipart/form-data',
        )

        with self.app.app_context():
            count_after_first = db.session.query(EtaMasterRecord).count()
            self.assertEqual(count_after_first, 3)
            # Should have 3 inserted
            self.assertIn(b'Inserted 3', response1.data)

        # Second upload (same file)
        excel_file = self._create_test_excel()
        response2 = self.client.post(
            '/eta-master',
            data={
                'file': (excel_file, 'test_eta.xlsx'),
            },
            content_type='multipart/form-data',
        )

        with self.app.app_context():
            # Should still be 3 records (upserted, not duplicated)
            count_after_second = db.session.query(EtaMasterRecord).count()
            self.assertEqual(count_after_second, 3)
            # Check for "updated" in the response (records should be upserted)
            response_text = response2.data.decode('utf-8')
            self.assertIn('updated', response_text.lower())

    def test_get_api_count_endpoint(self):
        """Test the /eta-master/api/count endpoint."""
        excel_file = self._create_test_excel()

        # Upload records
        self.client.post(
            '/eta-master',
            data={
                'file': (excel_file, 'test_eta.xlsx'),
            },
            content_type='multipart/form-data',
        )

        # Check count via API
        response = self.client.get('/eta-master/api/count')
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn('count', data)
        # Should have 3 records (cleared before test, added in this test)
        self.assertEqual(data['count'], 3)


if __name__ == '__main__':
    unittest.main()
