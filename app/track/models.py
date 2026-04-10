from app.models import Consignment, db


class TrackConsignment(db.Model):
    __table__ = Consignment.__table__
