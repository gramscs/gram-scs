import os
import unittest
from uuid import uuid4

from sqlalchemy import text

from app import create_app
from app.models import Consignment, db


class DatabaseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv("DATABASE_URL"):
            raise unittest.SkipTest("DATABASE_URL is required for database integration tests")

        cls.app = create_app()
        cls.app.config.update(TESTING=True)

    def test_database_responds_to_simple_query(self):
        with self.app.app_context():
            value = db.session.execute(text("SELECT 1")).scalar_one()
            self.assertEqual(value, 1)

    def test_consignment_table_is_queryable(self):
        with self.app.app_context():
            # Smoke query only; does not depend on fixture data.
            rows = Consignment.query.limit(1).all()
            self.assertIsInstance(rows, list)

    def test_consignment_create_read_delete_round_trip(self):
        test_number = f"T{uuid4().hex[:15]}"

        with self.app.app_context():
            entity = Consignment(
                consignment_number=test_number,
                status="In Transit",
                pickup_pincode="110017",
                drop_pincode="110018",
                eta="2099-01-01 00:00",
            )

            db.session.add(entity)
            db.session.commit()

            loaded = Consignment.query.filter_by(consignment_number=test_number).first()
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.status, "In Transit")

            db.session.delete(loaded)
            db.session.commit()

            deleted = Consignment.query.filter_by(consignment_number=test_number).first()
            self.assertIsNone(deleted)


if __name__ == "__main__":
    unittest.main()
