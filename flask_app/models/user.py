from flask_app import db
from flask_app import session_maker
from flask_app.config.default import Config
from .role import Role

class User(db.Model):
    __tablename__ = 'users'
    uid = db.Column(db.Integer, autoincrement=True, primary_key=True)
    username = db.Column(db.String(90), nullable=False)
    password = db.Column(db.String(32), nullable=False)
    email = db.Column(db.String(90))
    prediction = db.Column(db.JSON)
    detection = db.Column(db.JSON)
    fields = db.Column(db.JSON)
    redis_time = db.Column(db.Integer) 
    role = db.Column(db.String(100))
    role_id = db.Column(db.Integer) # admin  user

    def __repr__(self):
        return '<User %r>' % self.username

    def to_json(self, full=False, need_role=True):
        json_dict =  {
            "uid": self.uid,
            "username": self.username,
            # "email": self.email,
            # "prediction": self.prediction,
            # "detection": self.detection,
            # 'fields': self.fields,
            'redis_time': self.redis_time
        }

        if need_role and self.role_id:
            role = Role.get_by_id(self.role_id)
            json_dict['role'] = role.to_json() if role else None

        if full:
            json_dict['password'] = self.password
        
        return json_dict

    @classmethod
    def get_num(cls):
        with session_maker() as db_session:
            num = db_session.query(cls).count()
            return num

    @classmethod
    def add_user(cls, username, password, email, role_id):
        with session_maker() as db_session:
            prediction = Config.PREDICTION
            detection = Config.DETECTION
            user = User(username=username, password=password, email=email, redis_time=300,
                        prediction=prediction, detection=detection, role_id=role_id)
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            db_session.expunge(user)
            return user

    @classmethod
    def get_all(cls):
        with session_maker() as db_session:
            users = db_session.query(cls).all()
            total = 0
            for user in users:
                total += 1
                db_session.expunge(user)
            return users, total

    @classmethod
    def update_password(cls, uid, password):
        with session_maker() as db_session:
            user = db_session.query(cls).filter(cls.uid == uid).update({"password": password})
            return user

    @classmethod
    def delete_user(cls, username):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.username == username).delete()
            return username

    @classmethod
    def get_by_role_id(cls, role_id):
        with session_maker() as db_session:
            users = db_session.query(cls).filter(cls.role_id == role_id).all()  # 按照创建时间从新到旧排序
            for user in users:
                db_session.expunge(user)
            return users


    @classmethod
    def get_by_pages(cls, left, right):
        all_users, total = cls.get_all()
        selected_users = all_users[left: right]
        return selected_users, total

    @classmethod
    def get_by_username(cls, username):
        with session_maker() as db_session:
            user = db_session.query(cls).filter(cls.username == username).first()
            if not user:
                return None
            db_session.expunge(user)
            return user

    @classmethod
    def get_by_id(cls, uid):
        with session_maker() as db_session:
            user = db_session.query(cls).filter(cls.uid == uid).first()
            if not user:
                return None
            db_session.expunge(user)
            return user

    @classmethod
    def set_prediction(cls, uid, prediction):
        with session_maker() as db_session:
            user = db_session.query(cls).filter(cls.uid == uid).update({"prediction": prediction})
            return user

    @classmethod
    def set_detection(cls, uid, detection):
        with session_maker() as db_session:
            user = db_session.query(cls).filter(cls.uid == uid).update({"detection": detection})
            return user

    @classmethod
    def set_role(cls, uid, role_id):
        with session_maker() as db_session:
            user = db_session.query(cls).filter(cls.uid == uid).update({"role_id": role_id})
            return user

    @classmethod
    def set_fields(cls, uid, fields):
        with session_maker() as db_session:
            user = db_session.query(cls).filter(cls.uid == uid).update({"fields": fields})
            return user

    @classmethod
    def set_redis_time(cls, uid, redis_time):
        with session_maker() as db_session:
            user = db_session.query(cls).filter(cls.uid == uid).update({"redis_time": redis_time})
            return user

    @classmethod
    def search_by_pages(cls, uid,username, email, prediction, fields, role_id, left, right):
        users, total = cls.search(uid,username, email, prediction, fields, role_id)
        selected_users = users[left: right]
        return selected_users, total

    @classmethod
    def search(cls, uid,username, email, prediction, fields, role_id):
        query_list = list()
        if uid:
            query_list.append(cls.uid == uid)
        if username:
            query_list.append(cls.username.like('%'+username+'%'))
        if email:
            query_list.append(cls.email.like('%'+email+'%'))
        if prediction:
            query_list.append(cls.prediction.like('%'+prediction+'%'))            
        if fields:
            query_list.append(cls.fields.like('%'+fields+'%'))
        if role_id:
            query_list.append(cls.role_id == role_id)

        with session_maker() as db_session:
            filtered_users = db_session.query(cls).filter(*query_list).all()
            
            if filtered_users is None:
                return None
            
            total = 0
            for user in filtered_users:
                db_session.expunge(user)
                total += 1
            return filtered_users, total