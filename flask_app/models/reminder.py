# from datetime import datetime
import time
import datetime
from typing import Union

from flask_app import db, session_maker
from flask_app.models.model import Model
from flask_app.models.point_desc import PointDesc
from flask_app.models.user import User
from loguru import logger
import traceback
class Reminder(db.Model):
    __tablename__ = 'reminder'
    rid = db.Column(db.Integer, autoincrement=True, primary_key=True)
    rtype = db.Column(db.String(20), nullable=False)
    pid = db.Column(db.Integer, db.ForeignKey('point_desc.pid', ondelete='SET NULL'))
    mid = db.Column(db.Integer)
    version = db.Column(db.Integer)
    state = db.Column(db.Integer, nullable=False, default=0)
    create_time = db.Column(db.DateTime, nullable=False)
    confirm_time = db.Column(db.DateTime)
    archive_time = db.Column(db.DateTime)
    title = db.Column(db.Text)
    remark = db.Column(db.Text)
    confirm_user = db.Column(db.Integer, db.ForeignKey('users.uid', ondelete='SET NULL'))
    archive_user = db.Column(db.Integer, db.ForeignKey('users.uid', ondelete='SET NULL'))
    unit = db.Column(db.Integer, db.ForeignKey('unit_system.usid', ondelete='SET NULL'))
    first_report_flag = db.Column(db.Boolean)
    # TODO:该外键约束的定义没有起作用
    ref_cons = db.ForeignKeyConstraint(['mid', 'version'], ['model.mid', 'model.version'], ondelete='SET NULL')

    def to_json(self):
        json_dict = {
            "rid": self.rid,
            "title": self.title,
            "rtype": self.rtype,
            "state": self.state,
            "remark": self.remark,
            "point": None,
            "model": None,
            "create_time": datetime.datetime.timestamp(self.create_time),
            "confirm_time": datetime.datetime.timestamp(self.confirm_time) if self.confirm_time else None,
            "archive_time": datetime.datetime.timestamp(self.archive_time) if self.archive_time else None,
            "unit": self.unit if self.unit else None
        }

        if self.pid:
            point = PointDesc.get_by_id(self.pid, self.unit)
            if point:
                json_dict['point'] = point.to_json(full=False)
        
        if self.mid and self.version:
            model = Model.get_by_id_and_version(self.mid, self.version, self.unit)
            if model:
                json_dict['model'] = model.to_json()
            
        if self.confirm_user:
            c_user = User.get_by_id(self.confirm_user)
            if c_user:
                json_dict['confirm_user'] = c_user.to_json()
        
        if self.archive_user:
            a_user = User.get_by_id(self.archive_user)
            if a_user:
                json_dict['archive_user'] = a_user.to_json()

        return json_dict
    
    @classmethod
    def create_reminder(cls, rtype, pid, mid, version, title, remark, unit, state=0):
        with session_maker() as db_session:
            reminder = Reminder(rtype=rtype, pid=pid, mid=mid, version=version, title=title, remark=remark, state=state, create_time=datetime.datetime.now(), unit=unit)
            db_session.add(reminder)
            return
    
    @classmethod
    def create_reminders(cls, new_reminders):
        with session_maker() as db_session:
            for reminder_data in new_reminders:
                reminder_data['state'] = 0
                if 'create_time' not in reminder_data:
                    reminder_data['create_time'] = datetime.datetime.now()
                new_reminder = Reminder(**reminder_data)
                db_session.add(new_reminder)
            return
    
    @classmethod
    def delete_reminder(cls, rid):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.rid == rid).delete()
            return rid

    @classmethod
    def update_reminder(cls, rid, data):
        if len(data) == 0:
            return True, ''
        # 修改state应调用update_state()
        if 'state' in data:
            del data['state']

        with session_maker() as db_session:
            db_session.query(cls).filter(cls.rid == rid).update(data)
    
    @classmethod
    def update_state(cls, rid, unit, user_id, new_state):
        with session_maker() as db_session:
            target_reminder = db_session.query(cls).filter(cls.unit == unit, cls.rid == rid).first()
            if not target_reminder:
                return False, '找不到指定预警'
            
            # 确认操作
            if target_reminder.state == 0 and new_state == 1:
                target_reminder.confirm_time = datetime.datetime.now()
                target_reminder.confirm_user = user_id
                target_reminder.state = 1
            # 取消操作
            elif target_reminder.state == 1 and new_state == 0:
                target_reminder.confirm_time = None
                target_reminder.confirm_user = None
                target_reminder.state = 0
            # 归档操作
            elif target_reminder.state == 1 and new_state == 2:
                target_reminder.archive_time = datetime.datetime.now()
                target_reminder.archive_user = user_id
                target_reminder.state = 2
            else:
                return False, '非法的状态改变: {}->{}'.format(target_reminder.state, new_state)
            
        return True, ''

    @classmethod
    def get_all_in_unit(cls, unit):
        with session_maker() as db_session:
            # 默认不返回归档状态(state=2)的信息
            reminders = db_session.query(cls).filter(cls.unit == unit, cls.state < 2).order_by(cls.create_time.desc()).all()  # 按照创建时间从新到旧排序
            total = 0
            for reminder in reminders:
                total += 1
                db_session.expunge(reminder)
            return reminders, total
    
    @classmethod
    def get_in_unit_by_pages(cls, unit, page, size):
        with session_maker() as db_session:
            reminder_paginates = db_session.query(cls).filter(cls.unit == unit, cls.state < 2).order_by(cls.create_time.desc()).paginate(page=page, per_page=size, error_out=False)
            for rp in reminder_paginates.items:
                db_session.expunge(rp)
            
            return reminder_paginates.items, reminder_paginates.total

    @classmethod
    def get_by_id(cls, rid, unit):
        with session_maker() as db_session:
            reminder = db_session.query(cls).filter(cls.rid == rid, cls.unit == unit).first()
            if reminder:
                db_session.expunge(reminder)
            return reminder
    
    @classmethod
    def search(cls, mid, version, pid, rtype, model_name, point_name, state, unit, page=None, size=None):
        query_list = list()
        if mid and version:
            query_list.append(db.and_(cls.mid == mid, cls.version == version))
        if pid:
            query_list.append(cls.pid == pid)
        if rtype:
            query_list.append(cls.rtype == rtype)
        if model_name:
            query_list.append(db.and_(Model.name.like('%'+model_name+'%'), Model.mid == cls.mid, Model.version == cls.version))
        if point_name:
            query_list.append(db.and_(PointDesc.point_name.like('%'+point_name+'%'), PointDesc.pid == cls.pid))
        if state:
            query_list.append(cls.state == state)

        with session_maker() as db_session:
            filtered_reminders = db_session.query(cls).filter(*query_list, cls.unit == unit).order_by(cls.create_time.desc()).paginate(page=page, per_page=size, error_out=False)
            
            # if filtered_reminders.total == 0:
            #     return None, 0
            
            # final_reminders = list()
            for reminder in filtered_reminders.items:
                db_session.expunge(reminder)
                # final_reminders.append(reminder)

            return filtered_reminders.items, filtered_reminders.total
    
    @classmethod
    def get_unit_counts_by_days(cls, unit, day_diff) -> list:
        '''
        获取指定unit几天内每天的remider个数
        '''
        today = datetime.datetime.now()
        start_day = today - datetime.timedelta(days=day_diff)

        with session_maker() as db_session:
            n_reminders_per_day = db_session.query(db.func.min(cls.create_time), db.func.count(cls.rid))\
                                            .filter(cls.unit == unit, cls.create_time >= start_day)\
                                            .group_by(db.func.day(cls.create_time)).all()
            
            day_num_map = {day[0].date(): day[1] for day in n_reminders_per_day}
            
            res = list()
            day = start_day.date()
            while day < today.date() + datetime.timedelta(days=1):
                res.append({
                    'day': time.mktime(day.timetuple()),
                    'n_reminders': day_num_map.get(day, 0)
                })
                day += datetime.timedelta(days=1)
            
            return res
        
    
    @classmethod
    def clear(cls) -> Union[bool, str]:
        try:
            with session_maker() as db_session:
                db_session.execute('''TRUNCATE TABLE reminder''')
            return True, 'success'
        except Exception as e:
            logger.error(traceback.format_exc())
            return False, traceback.format_exc()