from flask_app import db, session_maker
from typing import Union
from flask_app.util.common.time_trans import *

class Indicator(db.Model):
    __tablename__ = 'indicator'
    iid = db.Column(db.Integer, autoincrement=True, primary_key=True)
    time = db.Column(db.DateTime, nullable=False)
    path = db.Column(db.String(60), nullable=False)
    size = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return '<Indicator %r>' % self.time

    def to_dict(self):
        return {
            'iid': self.iid,
            'time': Changestr(self.time),
            'path': self.path,
            'size': self.size
        }

    @classmethod
    def create(cls, time, path, size):
        indicator = Indicator(time=time, path=path, size=size)
        with session_maker() as db_session:
            db_session.add(indicator)
            db_session.flush()
            iid = indicator.iid
            return iid
    
    @classmethod
    def delete(cls, iid):
        with session_maker() as db_session:
            # res = db_session.query(cls).filter(cls.iid == iid).first()
            # if not res:
            #     return False, '指定的数据文件不存在'
            db_session.query(cls).filter(cls.iid == iid).delete()
    
    @classmethod
    def clear(cls):
        with session_maker() as db_session:
            db_session.query(cls).delete()

    @classmethod
    def get_by_id(cls, iid: Union[str, int]):
        with session_maker() as db_session:
            res = db_session.query(cls).filter(cls.iid == iid).first()
            if res:
                db_session.expunge(res)
            return res

    @classmethod
    def get_by_time_zone(cls, start_time: str, end_time: str):
        """ 时间格式： 2021-1-1 00:00:00 """
        st = Normaltime(start_time)
        ed = Normaltime(end_time)
        with session_maker() as db_session:
            res = db_session.query(cls).filter(cls.time.between(st, ed)).all()
            for r in res:
                db_session.expunge(r)
            return res, len(res)
    
    @classmethod
    def get_all(cls):
        with session_maker() as db_session:
            res = db_session.query(cls).all()
            for r in res:
                db_session.expunge(r)
            return res, len(res)
