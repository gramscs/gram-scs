import io
import os
import tempfile
import unittest

from openpyxl import Workbook

from app import create_app
from app.eta_master.models import EtaMasterRecord


class EtaMasterImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv('DATABASE_URL'):
            raise unittest.SkipTest('DATABASE_URL is required for ETA master integration tests')

        cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def _build_workbook(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'ETA Data'
        sheet.append([
            'Sno',
            'PIN CODE',
            'PICK UP STATION',
            'STATE/UT',
            'CITY',
            'PICK UP LOCATION',
            'DELIVERY LOCATION',
            'TAT In Days',
            'Zone',
        ])
        sheet.append([1, '110017', 'Saket Hub', 'Delhi', 'New Delhi', 'Delhi NCR', 'Mumbai', 2.5, 'North'])
        sheet.append([2, '400001', 'Mumbai Hub', 'Maharashtra', 'Mumbai', 'Mumbai Port', 'Delhi', 3, 'West'])

        temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        workbook.save(temp_file.name)
        temp_file.close()
        return temp_file.name

    def test_excel_import_creates_records(self):
        path = self._build_workbook()
        try:
            with open(path, 'rb') as file_handle:
                response = self.client.post(
                    '/eta-master',
                    data={'file': (io.BytesIO(file_handle.read()), 'eta_master.xlsx')},
                    content_type='multipart/form-data',
                )

            self.assertEqual(response.status_code, 200)
            with self.app.app_context():
                records = EtaMasterRecord.query.all()
                self.assertGreaterEqual(len(records), 2)
        finally:
            if os.path.exists(path):
                os.remove(path)


if __name__ == '__main__':
    unittest.main()
