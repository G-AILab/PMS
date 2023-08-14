from flask_app import db, session_maker
from flask_app.models.unit_system import UnitSystem


class SystemGraph(db.Model):
    __tablename__ = 'system_graph'
    gid = db.Column(db.Integer, autoincrement=True, primary_key=True)
    graph_name = path = db.Column(db.String(60), nullable=False)
    path = db.Column(db.Text)
    unit = db.Column(db.Integer, db.ForeignKey('unit_system.usid', ondelete='SET NULL'))
    DELETED = db.Column(db.Boolean, default=False)

    def to_json(self):
        json_dict =  {
            'gid': self.gid,
            'path': self.path,
            'graph_name': self.graph_name
        }

        if self.unit:
            json_dict['unit'] = UnitSystem.get_by_id(self.unit).to_json()
        
        return json_dict
    
    @classmethod
    def get_all_in_unit(cls, unit):
        with session_maker() as db_session:
            graphs = db_session.query(cls).filter(cls.unit == unit, cls.DELETED == False).all()
            total = 0
            for g in graphs:
                total += 1
                db_session.expunge(g)
            
            return graphs, total
    
    @classmethod
    def get_by_name(cls, name, unit):
        with session_maker() as db_session:
            target_graph = db_session.query(cls).filter(cls.graph_name == name, cls.unit == unit, cls.DELETED == False).first()
            if target_graph:
                db_session.expunge(target_graph)
            return target_graph
    
    @classmethod
    def get_by_id(cls, gid, unit):
        with session_maker() as db_session:
            target_graph = db_session.query(cls).filter(cls.gid == gid, cls.unit == unit, cls.DELETED == False).first()
            if target_graph:
                db_session.expunge(target_graph)
            return target_graph
    
    @classmethod
    def create(cls, name, path, unit):
        with session_maker() as db_session:
            new_graph = cls(graph_name=name, path=path, unit=unit, DELETED=False)
            db_session.add(new_graph)
            return
    
    @classmethod
    def update_graph(cls, gid, data):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.gid == gid).update(data)
    
    @classmethod
    def delete_by_id(cls, gid):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.gid == gid).update({'DELETED': True})
