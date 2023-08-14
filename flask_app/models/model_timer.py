

from flask_app import db
from flask_app import session_maker

class Model_timer(db.Model):
    __tablename__ = 'model_timer'
    mid = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.Integer, primary_key=True)
    select_start = db.Column(db.Integer)
    select_end = db.Column(db.Integer)
    train_start = db.Column(db.Integer)
    train_end = db.Column(db.Integer)
    optimize_start = db.Column(db.Integer)
    optimize_end = db.Column(db.Integer)
    export_start = db.Column(db.Integer)
    export_end = db.Column(db.Integer)

    fkey_mid = db.ForeignKeyConstraint(['mid', 'version'], ['model.mid', 'model.version'], ondelete='CASCADE')

    def __repr__(self) -> str:
        return '<Model_timer %r>' % str(self.mid) + "v" + str(self.version) + 'model_timer'

    def to_json(self):
        return {
            'select_start': self.select_start if self.select_start else None,
            'select_end': self.select_end if self.select_end else None,
            'train_start': self.train_start if self.train_start else None,
            'train_end': self.train_end if self.train_end else None,
            'optimize_start': self.optimize_start if self.optimize_start else None,
            'optimize_end': self.optimize_end if self.optimize_end else None,
            'export_start': self.export_start if self.export_start else None,
            'export_end': self.export_end if self.export_end else None
        }

    @classmethod
    def create(cls, mid, version):
        with session_maker() as db_session:
            model_timer = Model_timer(mid=mid, version=version, select_start=None, select_end=None, train_start=None, train_end=None,
                                      optimize_start=None, optimize_end=None, export_start=None, export_end=None)
            db_session.add(model_timer)
        return


    @classmethod
    def get_by_id_and_version(cls, mid, version):
        with session_maker() as db_session:
            model_timer = db_session.query(cls).filter(Model_timer.mid == mid, Model_timer.version == version).first()
            if model_timer is None:
                return None
            db_session.expunge(model_timer)
            return model_timer


    @classmethod
    def get(cls, mid, version, db_session):
        model_timer = db_session.query(cls).filter(Model_timer.mid == mid, Model_timer.version == version).first()
        if model_timer is None:
            return None
        return model_timer.to_json()


    @classmethod
    def update_timer(cls, mid, version, data):

        with session_maker() as db_session:
            db_session.query(cls).filter(Model_timer.mid == mid, Model_timer.version == version).update(data)
            return True


    @classmethod
    def delete(cls, mid, version):
        with session_maker() as db_session:
            db_session.query(cls).filter(Model_timer.mid == mid, Model_timer.version == version).delete()
            return

    @classmethod
    def update_timers(cls, update_args):
        with session_maker() as db_session:
            for update_data in update_args:
                if 'data' in update_data and 'mid' in update_data and 'version' in update_data:
                    mid = update_data['mid']
                    version = update_data['version']
                    data = update_data['data']
                    db_session.query(cls).filter(cls.mid == mid, cls.version == version).update(data)
            return True
