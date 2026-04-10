from app import create_app
from app.models import db


def migrate_legacy_consignment_columns():
    required_columns = {
        "pickup_pincode": "TEXT",
        "drop_pincode": "TEXT",
        "eta_debug_json": "TEXT",
    }

    app = create_app()
    with app.app_context():
        with db.engine.connect() as conn:
            columns_result = conn.exec_driver_sql("PRAGMA table_info(consignment)")
            existing_columns = {row[1] for row in columns_result.fetchall()}

            for column_name, column_type in required_columns.items():
                if column_name in existing_columns:
                    continue
                app.logger.info("Adding missing legacy column consignment.%s", column_name)
                conn.exec_driver_sql(
                    f"ALTER TABLE consignment ADD COLUMN {column_name} {column_type}"
                )

            conn.commit()


if __name__ == "__main__":
    migrate_legacy_consignment_columns()
