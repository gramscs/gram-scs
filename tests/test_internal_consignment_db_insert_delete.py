import os
import unittest
from uuid import uuid4


os.environ.setdefault("SECRET_KEY", "test-secret-key-for-db-insert-delete")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    "scrypt:32768:8:1$yFUNQ6eCe1ScMEcQ$d94441786edd350236b9340455e3302df2cbb8cf12ba94311abf8d2f1c52b75a20efc1c7a7a8ffaa0357c3b9e0f246dea70c4ea368f0346072f03f55325f913b",
)

from app import create_app
from app.models import Consignment, db


class InternalConsignmentDbInsertDeleteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv("DATABASE_URL"):
            raise unittest.SkipTest("DATABASE_URL is required for database integration tests")

        cls.app = create_app()
        cls.app.config.update(TESTING=True)

    def test_insert_and_delete_dummy_consignment(self):
        consignment_number = f"DBDEL{uuid4().hex[:8].upper()}"

        with self.app.app_context():
            row = Consignment(
                consignment_number=consignment_number,
                status="In Transit",
                pickup_pincode="110017",
                drop_pincode="400001",
                eta="2026-04-27 12:00",
            )
            db.session.add(row)
            db.session.commit()

            inserted = Consignment.query.filter_by(consignment_number=consignment_number).first()
            self.assertIsNotNone(inserted)

            db.session.delete(inserted)
            db.session.commit()

            deleted = Consignment.query.filter_by(consignment_number=consignment_number).first()
            self.assertIsNone(deleted)


if __name__ == "__main__":
    unittest.main()
