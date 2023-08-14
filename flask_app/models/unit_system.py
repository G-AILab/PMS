from flask_app import db
from flask_app import session_maker


class UnitSystem(db.Model):
    __tablename__ = 'unit_system'
    usid = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.Text)
    alias = db.Column(db.Text)
    prefix = db.Column(db.String(20))
    DELETED = db.Column(db.Boolean, default=False)

    def to_json(self):
        return {
            "usid": self.usid,
            "name": self.name,
            "alias": self.alias,
            "prefix": self.prefix
        }
    
    @classmethod
    def get_by_id(cls, usid):
        with session_maker() as db_session:
            unit = db_session.query(cls).filter(cls.usid == usid, cls.DELETED == False).first()
            if unit:
                db_session.expunge(unit)
            return unit
    
    @classmethod
    def get_by_page(cls, page=None, size=None):
        with session_maker() as db_session:
            units = db_session.query(cls).filter(cls.DELETED == False).paginate(page=page, per_page=size, error_out=False)

            queried_units = list()
            for unit in units.items:
                db_session.expunge(unit)
                queried_units.append(unit)
            
            return queried_units, units.total
    
    @classmethod
    def get_all(cls):
        with session_maker() as db_session:
            units = db_session.query(cls).filter(cls.DELETED == False).all()
            queried_units = list()
            for unit in units:
                db_session.expunge(unit)
                queried_units.append(unit)
            
            return queried_units, len(queried_units)
    
    @classmethod
    def create_unit(cls, name, alias, prefix):
        with session_maker() as db_session:
            sys_config = cls(name=name, alias=alias, prefix=prefix, DELETED=False)
            db_session.add(sys_config)
    
    @classmethod
    def update_unit(cls, usid, data):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.usid == usid, cls.DELETED == False).update(data)
    
    @classmethod
    def delete_unit(cls, usid):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.usid == usid).update({'DELETED': True})
