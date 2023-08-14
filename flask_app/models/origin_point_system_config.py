from typing import Dict

from flask_app import db
from flask_app import session_maker
from flask_app.models.relation_map import upsert_all


class OriginPointSystemConfig(db.Model):
    # __tablename__ = 'origin_point_system_config'
    # __table_args__ = {'extend_existing': True}
    # origin_point = db.Column(db.String(30), nullable=False, primary_key=True)
    # system_config = db.Column(db.Integer, primary_key=True)
    __table__ = db.Model.metadata.tables['origin_point_system_config']
    
    def __repr__(self):
        return '<OriginPointSystemConfig-{} {}>'.format(self.origin_point, self.system_config)
    
    def __eq__(self, other):
        return self.origin_point == other.origin_point and self.system_config == other.system_config
    
    def to_dict(self) -> Dict:  # type: ignore
        return {
            'origin_point': self.origin_point,
            'system_config': self.system_config
        }
        
    @classmethod
    def create_origin_point_system_config(cls, origin_point: str, system_config: int):
        with session_maker() as db_session:
            entity = OriginPointSystemConfig(origin_point=origin_point, system_config=system_config)
            db_session.add(entity)
            db_session.commit()
            # refresh 刷新session缓存对象
            db_session.refresh(entity)
            db_session.expunge(entity)
            return entity

    @classmethod
    def upsert_all(cls, records):
        upsert_all(cls, records=records)
