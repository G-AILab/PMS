from flask_app import db, session_maker
from flask_app.models.point_desc import PointDesc
from flask_app.models.system_graph import SystemGraph


class SystemGraphPoint(db.Model):
    __tablename__ = 'system_graph_point'
    gpid = db.Column(db.Integer, autoincrement=True, primary_key=True)
    x = db.Column(db.Integer)
    y = db.Column(db.Integer)
    graph = db.Column(db.Integer, db.ForeignKey('system_graph.gid', ondelete='SET NULL'))
    point = db.Column(db.Integer, db.ForeignKey('point_desc.pid', ondelete='SET NULL'))
    unit = db.Column(db.Integer, db.ForeignKey('unit_system.usid', ondelete='SET NULL'))
    DELETED = db.Column(db.Boolean, default=False)

    def to_json(self):
        json_dict =  {
            'gpid': self.gpid,
            'x': self.x,
            'y': self.y
        }

        if self.point and self.unit:
            target_point = PointDesc.get_by_id(self.point, self.unit)
            if target_point:
                json_dict['point'] = target_point.to_json(full=False)
        
        return json_dict
    
    @classmethod
    def get_all_in_unit(cls, unit):
        with session_maker() as db_session:
            graph_points = db_session.query(cls).filter(cls.unit == unit, cls.DELETED == False).all()
            total = 0
            for p in graph_points:
                total += 1
                db_session.expunge(p)
            
            return graph_points, total
    
    @classmethod
    def get_all_in_graph(cls, gid):
        with session_maker() as db_session:
            graph_points = db_session.query(cls).filter(cls.graph == gid, cls.DELETED == False).all()
            total = 0
            for p in graph_points:
                total += 1
                db_session.expunge(p)
            
            return graph_points, total
    
    @classmethod
    def get_by_id(cls, gpid, unit):
        with session_maker() as db_session:
            graph_point = db_session.query(cls).filter(cls.gpid == gpid, cls.unit == unit, cls.DELETED == False).first()
            if graph_point:
                db_session.expunge(graph_point)
            return graph_point
    
    @classmethod
    def create(cls, x, y, unit, graph, point=None):
        with session_maker() as db_session:
            new_graph_point = cls(x=x, y=y, unit=unit, graph=graph, point=point, DELETED=False)
            db_session.add(new_graph_point)
            return
    
    @classmethod
    def delete_by_id(cls, gpid):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.gpid == gpid).update({'DELETED': True})
    
    @classmethod
    def delete_points(cls, gpids):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.gpid.in_(gpids)).update({'DELETED': True})
    
    @classmethod
    def update_point(cls, gpid, data):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.gpid == gpid).update(data)
