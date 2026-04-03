from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

class Consignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    consignment_number = db.Column(db.String(16), unique=True, nullable=False)
    status = db.Column(db.String(200))
    pickup_pincode = db.Column(db.String(6))
    drop_pincode = db.Column(db.String(6))
    pickup_lat = db.Column(db.Float)
    pickup_lng = db.Column(db.Float)
    drop_lat = db.Column(db.Float)
    drop_lng = db.Column(db.Float)
    eta = db.Column(db.String(100))
    eta_debug_json = db.Column(db.Text)