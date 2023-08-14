from flask_app import db
from flask_app import session_maker
from flask_app.models.unit_system import UnitSystem


class SubSystem(db.Model):
    __tablename__ = 'sub_system'
    sid = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(40), nullable=False)
    member = db.Column(db.JSON)
    unit = db.Column(db.Integer, db.ForeignKey('unit_system.usid', ondelete='SET NULL'))
    DELETED = db.Column(db.Boolean, default=False)

    def to_json(self):
        json_dict = {
            "sid": self.sid,
            "name": self.name,
            "member": self.member
        }

        if self.unit is not None:
            json_dict['unit'] = UnitSystem.get_by_id(self.unit).to_json()
        
        return json_dict

    @classmethod
    def create_system(cls, name, member, unit):
        with session_maker() as db_session:
            system = SubSystem(name=name, member=member, unit=unit)
            db_session.add(system)
            db_session.commit()
            db_session.refresh(system)
            db_session.expunge(system)
            return system

    @classmethod
    def delete_system(cls, sid):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.sid == sid).update({'DELETED': True})
            return sid

    @classmethod
    def update_system(cls, sid, data):
        with session_maker() as db_session:
            if len(data) == 0:
                return False
            db_session.query(cls).filter(cls.sid == sid).update(data)
            return True

    @classmethod
    def get_all(cls):
        with session_maker() as db_session:
            systems = db_session.query(cls).all()
            return systems
    
    @classmethod
    def get_by_unit(cls, unit, page=None, size=None):
        with session_maker() as db_session:
            unit_systems = db_session.query(cls).filter(cls.unit == unit).paginate(page=page, per_page=size)
            for sys in unit_systems.items:
                db_session.expunge(sys)
            
            return unit_systems.items, unit_systems.total

    @classmethod
    def get_by_id(cls, sid):
        with session_maker() as db_session:
            system = db_session.query(cls).filter(cls.sid == sid).first()
            if system:
                db_session.expunge(system)
            return system
