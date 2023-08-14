from datetime import datetime
from flask_app import db
from flask_app import session_maker
import json
from json import JSONDecodeError
import decimal

class Dataset(db.Model):
    __tablename__ = 'dataset'
    did = db.Column(db.Integer, autoincrement=True, primary_key=True)
    sample_step = db.Column(db.Integer, nullable=False)
    path = db.Column(db.String(60), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    name = db.Column(db.String(30), nullable=False)
    null_points = db.Column(db.Text)
    static_points = db.Column(db.Text)
    status = db.Column(db.Integer)
    process = db.Column(db.Numeric(5,2))
    size = db.Column(db.Integer)
    all_points = db.Column(db.Text)
    append_status = db.Column(db.Integer)   #点名追加状态 -1:未追加 0：追加中 1：追加完成 2:追加失败
    append_process = db.Column(db.Numeric(5,2)) #点名追加进度
    update_status = db.Column(db.Integer)   #数据集更新状态 -1:未追加 0：追加中 1：追加完成 2:追加失败
    update_process = db.Column(db.Numeric(5,2)) #数据集更新进度

    def __repr__(self):
        return '<Dataset %r>' % self.did

    def to_json(self):
        start_time = datetime.timestamp(self.start_time)
        if self.end_time is not None:
            end_time = datetime.timestamp(self.end_time)
        else:
            end_time = datetime.timestamp(self.start_time)
        if self.status is not None:
            status = self.status
        else:
            status = 1
        if self.process is not None:
            process = self.process
        else:
            process = 100.00
        if self.append_process is not None:
            append_process = self.append_process
        else:
            append_process = 0.00
        if self.update_process is not None:
            update_process = self.update_process
        else:
            update_process = 0.00
        if self.size is not None:
            size = self.size
        else:
            size = -1
        try:
            all_points = json.loads(self.all_points)
        except JSONDecodeError:
            all_points = 'null_points字段格式错误!'
        except TypeError:
            all_points = ''
        try:
            null_points = json.loads(self.null_points)
        except JSONDecodeError:
            null_points = 'null_points字段格式错误!'
        except TypeError:
            null_points = ''
        try:
            static_points = json.loads(self.static_points)
        except JSONDecodeError:
            static_points = 'static_points字段格式错误!'
        except TypeError:
            static_points = ''
        if self.append_status is not None:
            append_status = self.append_status
        else:
            append_status = -1
        if self.update_status is not None:
            update_status = self.update_status
        else:
            update_status = -1
        return {
            'id': self.did,
            'sample_step': self.sample_step,
            'path': self.path,
            'start_time': start_time,
            'end_time': end_time,
            'name': self.name,
            'null_points': null_points,
            'static_points': static_points,
            'all_points': all_points,
            'status': status,
            'process': str(decimal.Decimal(process).quantize(decimal.Decimal('0.00'))),
            'size': size,
            'append_status': append_status,
            'append_process': append_process,
            'update_status': update_status,
            'update_process': update_process
        }

    @classmethod
    def get_by_id(cls, did):
        with session_maker() as db_session:
            data_set = db_session.query(Dataset).get(did)
            if data_set is not None:
                db_session.expunge(data_set)
            return data_set

    @classmethod
    def get_all(cls):
        with session_maker() as db_session:
            datasets = db_session.query(cls)
            total = 0
            for _ in datasets:
                total += 1
            return datasets, total

    @classmethod
    def get_by_page(cls, left, right):
        with session_maker() as db_session:
            datasets = db_session.query(cls)
            total = 0
            selected_datasets = datasets[left: right]
            for dataset in datasets:
                db_session.expunge(dataset)
                total += 1
            return selected_datasets, total

    @classmethod
    def add(cls, sample_step, path, start_time, end_time, name, null_points=None, static_points=None, status=0, process=0.00, size=-1, all_points=None, append_status=-1, append_process=0.00,
            update_status=-1, update_process=0.00):
        with session_maker() as db_session:
            dataset = Dataset(sample_step=sample_step,
                              path=path,
                              start_time=start_time,
                              end_time=end_time,
                              name=name,
                              null_points = null_points,
                              static_points = static_points,
                              all_points = all_points,
                              status = status,
                              process = process,
                              size = size,
                              append_status=append_status,
                              append_process=append_process,
                              update_status=update_status,
                              update_process=update_process)
            db_session.add(dataset)
            db_session.flush()
            did = dataset.did
            return did


    @classmethod
    def delete(cls, did):
        with session_maker() as db_session:
            db_session.query(Dataset).filter(Dataset.did == did).delete()
            return

    @classmethod
    def update_info(cls, did, data):
        with session_maker() as db_session:
            db_session.query(Dataset).filter(Dataset.did == did).update(data)
            return
    
    @classmethod
    def search_all(cls, name, page=None, size=None):
        with session_maker() as db_session:
            datasets = db_session.query(cls).filter((cls.name.like('%'+name+'%'))).paginate(page=page, per_page=size, error_out=False)
            for dataset in datasets.items:
                db_session.expunge(dataset)
            return datasets.items, datasets.total
    
    @classmethod
    def get_by_name(cls, name, left, right):
        with session_maker() as db_session:
            datasets = db_session.query(cls).filter((cls.name.like('%'+name+'%')))
            if not datasets:
                return None, 0
            total = 0
            selected_datasets = datasets[left: right]
            for dataset in datasets:
                db_session.expunge(dataset)
                total += 1
            return selected_datasets, total
