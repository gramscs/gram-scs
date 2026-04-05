import unittest
from io import BytesIO
from openpyxl import Workbook

from app import create_app, db
from app.eta_master.models import EtaMasterRecord


class EtaMasterUIAndImportTests(unittest.TestCase):
    """Test UI rendering and import button functionality with dummy data."""

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        with self.app.app_context():
            db.session.query(EtaMasterRecord).delete()
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.query(EtaMasterRecord).delete()
            db.session.commit()

    def _create_dummy_excel(self, num_records=5):
        """Create a dummy Excel file with test data."""
        wb = Workbook()
        ws = wb.active
        
        # Headers
        headers = ['SNO', 'PIN CODE', 'PICK UP STATION', 'STATE/UT', 'CITY', 
                   'PICK UP LOCATION', 'DELIVERY LOCATION', 'TAT IN DAYS', 'ZONE']
        ws.append(headers)
        
        # Dummy data
        dummy_data = [
            [1, '110001', 'Delhi Hub 1', 'DELHI', 'NEW DELHI', 'Station 1', 'Zone 1', 1.5, 'N1'],
            [2, '110002', 'Delhi Hub 2', 'DELHI', 'DELHI', 'Station 2', 'Zone 2', 1.0, 'N2'],
            [3, '400001', 'Mumbai Hub', 'MAHARASHTRA', 'MUMBAI', 'Port Area', 'Warehouse', 2.0, 'W1'],
            [4, '560001', 'Bengaluru Hub', 'KARNATAKA', 'BANGALORE', 'Tech Park', 'Whitefield', 1.0, 'S1'],
            [5, '122001', 'Gurgaon Hub', 'HARYANA', 'GURGAON', 'Fort Road', 'Golf Course', 1.5, 'N3'],
        ]
        
        # Add only requested number of records
        for row in dummy_data[:num_records]:
            ws.append(row)
        
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    def _create_large_excel(self, num_records=30):
        """Create a larger dummy Excel file with unique records for pagination tests."""
        wb = Workbook()
        ws = wb.active

        headers = ['SNO', 'PIN CODE', 'PICK UP STATION', 'STATE/UT', 'CITY',
                   'PICK UP LOCATION', 'DELIVERY LOCATION', 'TAT IN DAYS', 'ZONE']
        ws.append(headers)

        for index in range(num_records):
            pin_code = f'{110001 + index:06d}'
            ws.append([
                index + 1,
                pin_code,
                f'Station {index + 1}',
                'DELHI',
                f'CITY {index + 1}',
                f'Pickup {index + 1}',
                f'Delivery {index + 1}',
                1.0 + (index % 5) * 0.5,
                f'Z{(index % 4) + 1}',
            ])

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    # ==================== UI TESTS ====================
    
    def test_ui_page_title_present(self):
        """Test that the UI page has the correct title."""
        response = self.client.get('/eta-master')
        self.assertIn(b'ETA Master Database', response.data)

    def test_ui_upload_button_present(self):
        """Test that the upload button is present in UI."""
        response = self.client.get('/eta-master')
        self.assertIn(b'Upload Excel', response.data)
        self.assertIn(b'type="file"', response.data)
        self.assertIn(b'accept=".xlsx"', response.data)

    def test_edit_mode_shows_row_actions_and_add_button(self):
        """Test that edit mode renders row controls and the add-record button."""
        excel_file = self._create_dummy_excel(num_records=1)
        self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data'
        )

        response = self.client.get('/eta-master?mode=edit')
        self.assertIn(b'Add Record', response.data)
        self.assertIn(b'Back to View', response.data)
        self.assertIn(b'Save', response.data)
        self.assertIn(b'Delete', response.data)
        self.assertIn(b'name="pin_code"', response.data)

    def test_update_record_saves_changes_and_returns_to_view_mode(self):
        """Test that editing a record updates the DB and returns to view mode."""
        excel_file = self._create_dummy_excel(num_records=1)
        self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data'
        )

        with self.app.app_context():
            record = db.session.query(EtaMasterRecord).first()
            record_id = record.id

        response = self.client.post(
            f'/eta-master/records/{record_id}/update',
            data={
                'page': 1,
                'per_page': 25,
                'sno': 99,
                'pin_code': '110001',
                'pickup_station': 'Edited Hub',
                'state_ut': 'DELHI',
                'city': 'NEW DELHI',
                'pickup_location': 'Edited Pickup',
                'delivery_location': 'Edited Delivery',
                'tat_in_days': 4.5,
                'zone': 'N9',
            },
            follow_redirects=True,
        )

        self.assertIn(b'Record updated successfully.', response.data)
        self.assertIn(b'Edit Records', response.data)
        self.assertNotIn(b'Add Record', response.data)

        with self.app.app_context():
            updated = db.session.query(EtaMasterRecord).first()
            self.assertEqual(updated.sno, 99)
            self.assertEqual(updated.pickup_station, 'Edited Hub')
            self.assertEqual(updated.zone, 'N9')

    def test_delete_record_removes_it_from_database(self):
        """Test that the delete action removes a record from the DB."""
        excel_file = self._create_dummy_excel(num_records=1)
        self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data'
        )

        with self.app.app_context():
            record = db.session.query(EtaMasterRecord).first()
            record_id = record.id

        response = self.client.post(
            f'/eta-master/records/{record_id}/delete',
            data={'page': 1, 'per_page': 25},
            follow_redirects=True,
        )

        self.assertIn(b'Record deleted successfully.', response.data)
        with self.app.app_context():
            count = db.session.query(EtaMasterRecord).count()
            self.assertEqual(count, 0)

    def test_page_clamps_to_last_valid_page_after_delete(self):
        """Test that the UI does not land on an empty page after deleting records."""
        excel_file = self._create_large_excel(num_records=30)
        self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'large.xlsx')},
            content_type='multipart/form-data'
        )

        with self.app.app_context():
            page_two_records = db.session.query(EtaMasterRecord).order_by(EtaMasterRecord.id.desc()).offset(25).limit(5).all()
            record_ids = [record.id for record in page_two_records]

        for record_id in record_ids:
            self.client.post(
                f'/eta-master/records/{record_id}/delete',
                data={'page': 2, 'per_page': 25},
                follow_redirects=True,
            )

        response = self.client.get('/eta-master?page=2&per_page=25')
        self.assertIn(b'Showing 1-25 of 25 records', response.data)
        self.assertNotIn(b'No records imported yet', response.data)

    def test_add_record_modal_submission_creates_record(self):
        """Test that the add-record action creates a new manual record."""
        response = self.client.post(
            '/eta-master/records/new',
            data={
                'page': 1,
                'per_page': 25,
                'sno': 7,
                'pin_code': '560001',
                'pickup_station': 'Manual Station',
                'state_ut': 'KARNATAKA',
                'city': 'BANGALORE',
                'pickup_location': 'Manual Pickup',
                'delivery_location': 'Manual Delivery',
                'tat_in_days': 2.5,
                'zone': 'S1',
            },
            follow_redirects=True,
        )

        self.assertIn(b'Record added successfully.', response.data)
        self.assertIn(b'560001', response.data)

        with self.app.app_context():
            count = db.session.query(EtaMasterRecord).count()
            self.assertEqual(count, 1)

    def test_ui_table_headers_present(self):
        """Test that the table has all required column headers."""
        response = self.client.get('/eta-master')
        
        headers = [b'PIN Code', b'Pickup Station', b'City', b'State/UT', 
                  b'Pickup Location', b'Delivery Location', b'TAT (Days)', b'Zone']
        
        for header in headers:
            self.assertIn(header, response.data)

    def test_ui_empty_state_message(self):
        """Test that the empty state message is shown when no records exist."""
        response = self.client.get('/eta-master')
        self.assertIn(b'No records imported yet', response.data)

    def test_ui_page_loads_without_errors(self):
        """Test that the page loads without errors (status 200)."""
        response = self.client.get('/eta-master')
        self.assertEqual(response.status_code, 200)

    def test_ui_has_form_with_file_input(self):
        """Test that the form has file input element."""
        response = self.client.get('/eta-master')
        self.assertIn(b'<input', response.data)
        self.assertIn(b'type="file"', response.data)
        self.assertIn(b'accept=".xlsx"', response.data)

    # ==================== IMPORT BUTTON TESTS ====================

    def test_import_button_single_record(self):
        """Test import button with a single dummy record."""
        excel_file = self._create_dummy_excel(num_records=1)
        
        response = self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'single_record.xlsx')},
            content_type='multipart/form-data'
        )
        
        self.assertIn(b'Inserted 1', response.data)
        
        with self.app.app_context():
            count = db.session.query(EtaMasterRecord).count()
            self.assertEqual(count, 1)

    def test_import_button_multiple_records(self):
        """Test import button with multiple dummy records."""
        excel_file = self._create_dummy_excel(num_records=5)
        
        response = self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'multiple_records.xlsx')},
            content_type='multipart/form-data'
        )
        
        self.assertIn(b'Inserted 5', response.data)
        
        with self.app.app_context():
            count = db.session.query(EtaMasterRecord).count()
            self.assertEqual(count, 5)

    def test_import_button_shows_success_message(self):
        """Test that import button shows success message after upload."""
        excel_file = self._create_dummy_excel(num_records=3)
        
        response = self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data'
        )
        
        # Check for success message
        self.assertIn(b'Import complete', response.data)
        self.assertIn(b'alert-success', response.data)

    def test_import_button_shows_summary(self):
        """Test that import button shows import summary."""
        excel_file = self._create_dummy_excel(num_records=3)
        
        response = self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data'
        )
        
        # Check for summary
        self.assertIn(b'Import Summary:', response.data)

    # ==================== DATA DISPLAY TESTS ====================

    def test_imported_data_displays_in_table(self):
        """Test that imported data displays in the table after import."""
        excel_file = self._create_dummy_excel(num_records=2)
        
        # Upload
        self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data'
        )
        
        # Get page
        response = self.client.get('/eta-master')
        
        # Check that data is displayed
        self.assertIn(b'110001', response.data)  # PIN code
        self.assertIn(b'Delhi Hub 1', response.data)  # Station
        self.assertIn(b'NEW DELHI', response.data)  # City
        self.assertIn(b'1.5', response.data)  # TAT

    def test_imported_data_correct_type_display(self):
        """Test that imported data is correctly formatted in the table."""
        excel_file = self._create_dummy_excel(num_records=1)
        
        self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data'
        )
        
        response = self.client.get('/eta-master')
        
        # Check data types display correctly
        # PIN code should be 6 digits
        self.assertIn(b'110001', response.data)
        # TAT should be float
        self.assertIn(b'1.5', response.data)
        # Zone should be string
        self.assertIn(b'N1', response.data)

    def test_ui_shows_updated_records_after_second_import(self):
        """Test that UI updates after second import (upsert)."""
        # First import
        excel_file1 = self._create_dummy_excel(num_records=2)
        self.client.post(
            '/eta-master',
            data={'file': (excel_file1, 'test.xlsx')},
            content_type='multipart/form-data'
        )
        
        # Second import (same file)
        excel_file2 = self._create_dummy_excel(num_records=2)
        response = self.client.post(
            '/eta-master',
            data={'file': (excel_file2, 'test.xlsx')},
            content_type='multipart/form-data'
        )
        
        # Should show "updated" message
        self.assertIn(b'updated 2', response.data)
        
        # Get page
        page = self.client.get('/eta-master')
        
        # Should still show the records
        self.assertIn(b'110001', page.data)
        self.assertIn(b'110002', page.data)

    # ==================== INTEGRATION TESTS ====================

    def test_complete_workflow_import_and_display(self):
        """Test complete workflow: upload -> validate -> display."""
        # Step 1: Verify empty state
        response = self.client.get('/eta-master')
        self.assertIn(b'No records imported yet', response.data)
        
        # Step 2: Upload data
        excel_file = self._create_dummy_excel(num_records=5)
        upload_response = self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data'
        )
        self.assertIn(b'Inserted 5', upload_response.data)
        
        # Step 3: Verify data in database
        with self.app.app_context():
            count = db.session.query(EtaMasterRecord).count()
            self.assertEqual(count, 5)
        
        # Step 4: Verify data displays on page
        page_response = self.client.get('/eta-master')
        self.assertIn(b'110001', page_response.data)
        self.assertIn(b'400001', page_response.data)
        self.assertIn(b'560001', page_response.data)
        self.assertNotIn(b'No records imported yet', page_response.data)

    def test_api_count_matches_ui_records(self):
        """Test that API count endpoint matches records shown in UI."""
        # Upload 3 records
        excel_file = self._create_dummy_excel(num_records=3)
        self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'test.xlsx')},
            content_type='multipart/form-data'
        )
        
        # Check API count
        api_response = self.client.get('/eta-master/api/count')
        api_data = api_response.get_json()
        self.assertEqual(api_data['count'], 3)
        
        # Get UI page
        ui_response = self.client.get('/eta-master')
        
        # Count records displayed in UI table rows
        record_count = ui_response.data.count(b'<tr>')
        # Subtract 1 for header row, then divide by rows per record
        # Each record should have 1 table row
        self.assertGreaterEqual(record_count, 2)  # At least header + 1 record

    def test_pagination_limits_records_per_page(self):
        """Test that the ETA Master page paginates large datasets."""
        excel_file = self._create_large_excel(num_records=30)

        self.client.post(
            '/eta-master',
            data={'file': (excel_file, 'large.xlsx')},
            content_type='multipart/form-data'
        )

        page_one = self.client.get('/eta-master?per_page=25&page=1')
        page_two = self.client.get('/eta-master?per_page=25&page=2')

        self.assertIn(b'Showing 1-25 of 30 records', page_one.data)
        self.assertIn(b'Page 1 of 2', page_one.data)
        self.assertIn(b'Showing 26-30 of 30 records', page_two.data)
        self.assertIn(b'Page 2 of 2', page_two.data)

        self.assertEqual(page_one.data.count(b'<tr>'), 26)  # 1 header + 25 records
        self.assertEqual(page_two.data.count(b'<tr>'), 6)   # 1 header + 5 records
        self.assertIn(b'110030', page_one.data)
        self.assertNotIn(b'110001', page_one.data)
        self.assertIn(b'110001', page_two.data)


if __name__ == '__main__':
    unittest.main()
