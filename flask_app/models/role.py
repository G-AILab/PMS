from flask_app import db
from flask_app import session_maker
from flask_app.config.default import Config
from enum import Enum
class System(Enum):
    Index = 0
    Model = 1
    SubSystemMonitor = 2
    DataSet = 3
    SubSystemManage = 4
    Point = 5
    Reminder = 6

ALL_SYSTEMS_PAGE = {
    0 : "首页",
    1 : "模型管理",
    2 : "子系统监控",
    3 : "数据集管理",
    4 : "子系统管理",
    5 : "点名管理",
    6 : "预警管理",
}

class Role(db.Model):
    __tablename__ = 'role'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    systems = db.Column(db.JSON)

    def __repr__(self):
        return '<Role %r>' % self.name

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            'systems' : self.systems
        }

    @classmethod
    def get_num(cls):
        with session_maker() as db_session:
            num = db_session.query(cls).count()
            return num

    @classmethod
    def get_all(cls):
        with session_maker() as db_session:
            roles = db_session.query(cls)
            total = 0
            for role in roles:
                total += 1
                db_session.expunge(role)
            return roles, total

    @classmethod
    def add_role(cls, name, systems):
        with session_maker() as db_session:
            role = Role(name=name, systems=systems)
            db_session.add(role)
            db_session.commit()
            db_session.refresh(role)
            db_session.expunge(role)
            return role

    @classmethod
    def get_by_pages(cls, left, right):
        all_roles, total = cls.get_all()
        selected_roles = all_roles[left: right]
        return selected_roles, total

    @classmethod
    def delete_role(cls, id):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.id == id).delete()
            return id
            
    @classmethod
    def get_by_name(cls, name):
        with session_maker() as db_session:
            role = db_session.query(cls).filter(cls.name == name).first()
            if not role:
                return None
            db_session.expunge(role)
            return role

    @classmethod
    def get_by_id(cls, rid):
        with session_maker() as db_session:
            role = db_session.query(cls).filter(cls.id == rid).first()
            if not role:
                return None
            db_session.expunge(role)
            return role

    @classmethod
    def set_systems(cls, rid, systems):
        with session_maker() as db_session:
            role = db_session.query(cls).filter(cls.id == rid).update({"systems": systems})
            return role

    @classmethod
    def set_name(cls, rid, name):
        with session_maker() as db_session:
            role = db_session.query(cls).filter(cls.id == rid).update({"name": name})
            return role