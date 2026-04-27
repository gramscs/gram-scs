import os
import unittest
from uuid import uuid4

from app import create_app
from app.admin.auth import ADMIN_SESSION_KEY
from app.models import Lead, db


class ContactFormHomepageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv("DATABASE_URL"):
            raise unittest.SkipTest("DATABASE_URL is required for tests")

        cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def test_homepage_contact_form_targets_contact_route(self):
        response = self.client.get("/?test_bust=1")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'action="/contact"', response.data)
        self.assertIn(b'name="name"', response.data)
        self.assertIn(b'name="email"', response.data)
        self.assertIn(b'name="message"', response.data)
        self.assertIn(b'name="source" value="homepage"', response.data)

    def test_homepage_contact_submission_creates_lead_row(self):
        unique_email = f"lead-{uuid4().hex[:8]}@example.com"

        response = self.client.post(
            "/contact",
            data={
                "source": "homepage",
                "name": "Test User",
                "email": unique_email,
                "phone": "9999999999",
                "subject": "Homepage Contact",
                "message": "Please contact me",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/#contact"))

        with self.app.app_context():
            created = Lead.query.filter_by(email=unique_email).order_by(Lead.id.desc()).first()
            self.assertIsNotNone(created)
            self.assertEqual(created.name, "Test User")
            self.assertEqual(created.phone, "9999999999")
            self.assertEqual(created.subject, "Homepage Contact")
            self.assertEqual(created.message, "Please contact me")

            db.session.delete(created)
            db.session.commit()

    def test_admin_leads_page_loads(self):
        with self.client.session_transaction() as session_data:
            session_data[ADMIN_SESSION_KEY] = True

        response = self.client.get("/admin/leads")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Customer Leads", response.data)


if __name__ == "__main__":
    unittest.main()
