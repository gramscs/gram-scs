from datetime import datetime
import hashlib

from app.models import db


class EtaMasterRecord(db.Model):
    __bind_key__ = 'master'
    __tablename__ = 'eta_master_records'

    id = db.Column(db.Integer, primary_key=True)
    record_key = db.Column(db.String(128), unique=True, nullable=False, index=True)
    sno = db.Column(db.Integer)
    pin_code = db.Column(db.String(10), nullable=False, index=True)
    pickup_station = db.Column(db.String(255), nullable=False)
    state_ut = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    pickup_location = db.Column(db.String(255), nullable=False)
    delivery_location = db.Column(db.String(255), nullable=False)
    tat_in_days = db.Column(db.Float, nullable=False)
    zone = db.Column(db.String(50), nullable=False)
    source_filename = db.Column(db.String(255))
    source_row_number = db.Column(db.Integer)
    imported_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @staticmethod
    def build_record_key(*parts):
        normalized = [str(part or '').strip().lower() for part in parts]
        joined = '|'.join(normalized)
        return hashlib.sha256(joined.encode('utf-8')).hexdigest()
