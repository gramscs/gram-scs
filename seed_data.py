from app import create_app
from app.models import Consignment, Lead, db
from sqlalchemy.exc import IntegrityError, OperationalError
import logging
import sys

logger = logging.getLogger(__name__)

LOCAL_CONSIGNMENTS = [
    {
        "consignment_number": "LOCAL0001",
        "status": "Pickup Scheduled",
        "pickup_pincode": "110001",
        "pickup_address": "Gram SCS Delhi Pickup Hub, Connaught Place, New Delhi",
        "pickup_tag": "Delhi Hub",
        "pickup_date": "2026-06-19",
        "drop_pincode": "400001",
        "drop_address": "Nariman Point Business District, Mumbai",
        "drop_tag": "Mumbai Client",
        "drop_date": "2026-06-22",
        "eta": "2026-06-22 18:00",
    },
    {
        "consignment_number": "LOCAL0002",
        "status": "In Transit",
        "pickup_pincode": "560001",
        "pickup_address": "MG Road Fulfilment Center, Bengaluru",
        "pickup_tag": "Bengaluru FC",
        "pickup_date": "2026-06-17",
        "drop_pincode": "600001",
        "drop_address": "Chennai Port Receiving Dock, Chennai",
        "drop_tag": "Chennai Dock",
        "drop_date": "2026-06-20",
        "eta": "2026-06-20 15:30",
    },
    {
        "consignment_number": "LOCAL0003",
        "status": "Out for Delivery",
        "pickup_pincode": "411001",
        "pickup_address": "Pune Industrial Warehouse, Pune",
        "pickup_tag": "Pune Warehouse",
        "pickup_date": "2026-06-16",
        "drop_pincode": "421001",
        "drop_address": "Ulhasnagar Retail Distribution Point, Thane",
        "drop_tag": "Thane Retail",
        "drop_date": "2026-06-19",
        "eta": "2026-06-19 17:45",
    },
    {
        "consignment_number": "LOCAL0004",
        "status": "Delivered",
        "pickup_pincode": "700001",
        "pickup_address": "Kolkata Central Logistics Park, Kolkata",
        "pickup_tag": "Kolkata Park",
        "pickup_date": "2026-06-14",
        "drop_pincode": "751001",
        "drop_address": "Bhubaneswar Corporate Tower, Bhubaneswar",
        "drop_tag": "Bhubaneswar HQ",
        "drop_date": "2026-06-18",
        "eta": "2026-06-18 11:15",
    },
    {
        "consignment_number": "LOCAL0005",
        "status": "Delayed / On Hold",
        "pickup_pincode": "380001",
        "pickup_address": "Ahmedabad Packaging Unit, Ahmedabad",
        "pickup_tag": "Ahmedabad Unit",
        "pickup_date": "2026-06-15",
        "drop_pincode": "302001",
        "drop_address": "Jaipur Customer Experience Center, Jaipur",
        "drop_tag": "Jaipur CEC",
        "drop_date": "2026-06-21",
        "eta": "2026-06-21 12:00",
    },
]

LOCAL_LEADS = [
    Lead(name="Aarav Mehta", email="aarav.mehta@example.com", phone="+91 98765 43210", subject="Warehouse Enquiry", message="Need details for 3PL warehousing in Mumbai."),
    Lead(name="Priya Nair", email="priya.nair@example.com", phone="+91 98111 22334", subject="Transport Partnership", message="Looking for a long-term transport partner for South India routes."),
    Lead(name="Global Imports LLC", email="ops@globalimports.example", phone="+1 (415) 555-0198", subject="International Freight", message="Requesting a callback about import clearance and freight forwarding."),
]


def seed_local_data(reset=False):
    with create_app().app_context():
        try:
            if reset:
                logger.info("Clearing existing local seed data...")
                Consignment.query.delete()
                Lead.query.delete()

            existing_numbers = {row[0] for row in Consignment.query.with_entities(Consignment.consignment_number).all()}
            consignments = [Consignment(**payload) for payload in LOCAL_CONSIGNMENTS if payload["consignment_number"] not in existing_numbers]
            db.session.add_all(consignments)

            existing_emails = {row[0] for row in Lead.query.with_entities(Lead.email).all()}
            leads = [lead for lead in LOCAL_LEADS if lead.email not in existing_emails]
            db.session.add_all(leads)
            db.session.commit()

            print(f"✓ Added {len(consignments)} local test consignments and {len(leads)} leads.")
            print("\nTrack page test consignments:")
            for item in LOCAL_CONSIGNMENTS:
                print(f"  - {item['consignment_number']} ({item['status']})")
        except (IntegrityError, OperationalError) as error:
            db.session.rollback()
            logger.error("Database error while seeding local data: %s", error)
            sys.exit(1)
        except Exception as error:
            db.session.rollback()
            logger.error("Unexpected error while seeding local data: %s", error, exc_info=True)
            sys.exit(1)


if __name__ == "__main__":
    seed_local_data(reset="--reset" in sys.argv)
