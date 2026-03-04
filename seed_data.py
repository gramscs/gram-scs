from app import create_app
from app.models import db, Consignment
from sqlalchemy.exc import IntegrityError, OperationalError
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    app = create_app()

    with app.app_context():
        try:
            # Clear existing data
            logger.info("Clearing existing consignments...")
            Consignment.query.delete()
            
            # Add dummy consignments
            consignments = [
                Consignment(
                    consignment_number="GRAM-SCS-2024-001",
                    status="In Transit",
                    pickup_lat=28.6139,
                    pickup_lng=77.2090,  # Delhi
                    drop_lat=19.0760,
                    drop_lng=72.8777,    # Mumbai
                    eta="2024-03-05 14:30"
                ),
                Consignment(
                    consignment_number="GRAM-SCS-2024-002",
                    status="Out for Delivery",
                    pickup_lat=12.9716,
                    pickup_lng=77.5946,  # Bangalore
                    drop_lat=13.0827,
                    drop_lng=80.2707,    # Chennai
                    eta="2024-03-04 18:00"
                ),
                Consignment(
                    consignment_number="GRAM-SCS-2024-003",
                    status="Delivered",
                    pickup_lat=22.5726,
                    pickup_lng=88.3639,  # Kolkata
                    drop_lat=26.9124,
                    drop_lng=75.7873,    # Jaipur
                    eta="2024-03-03 10:00"
                ),
                Consignment(
                    consignment_number="GRAM-SCS-2024-004",
                    status="Pickup Scheduled",
                    pickup_lat=23.0225,
                    pickup_lng=72.5714,  # Ahmedabad
                    drop_lat=17.3850,
                    drop_lng=78.4867,    # Hyderabad
                    eta="2024-03-06 09:00"
                ),
                Consignment(
                    consignment_number="GRAM-SCS-2024-005",
                    status="In Transit",
                    pickup_lat=18.5204,
                    pickup_lng=73.8567,  # Pune
                    drop_lat=21.1458,
                    drop_lng=79.0882,    # Nagpur
                    eta="2024-03-05 16:45"
                )
            ]
            
            logger.info(f"Adding {len(consignments)} dummy consignments...")
            for consignment in consignments:
                db.session.add(consignment)
            
            db.session.commit()
            logger.info(f"✓ Successfully added {len(consignments)} dummy consignments to the database")
            print("\nTest with these consignment numbers:")
            for c in consignments:
                print(f"  - {c.consignment_number} ({c.status})")
        
        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"Database integrity error (duplicate data?): {e}")
            sys.exit(1)
        
        except OperationalError as e:
            db.session.rollback()
            logger.error(f"Database operational error: {e}")
            sys.exit(1)
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Unexpected error while seeding data: {e}", exc_info=True)
            sys.exit(1)

except Exception as e:
    logger.error(f"Failed to create application: {e}", exc_info=True)
    sys.exit(1)
