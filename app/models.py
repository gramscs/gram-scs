from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

class Consignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    consignment_number = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(200))
    pickup_lat = db.Column(db.Float)
    pickup_lng = db.Column(db.Float)
    drop_lat = db.Column(db.Float)
    drop_lng = db.Column(db.Float)
    eta = db.Column(db.String(100))