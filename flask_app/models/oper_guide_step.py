import datetime
from typing import Union

from flask_app import db
from flask_app import session_maker
from flask_app.models.system_config import SystemConfig
from flask_app.models.user import User
# from flask_app.models.oper_guide_system import OperGuideSystem


class OperGuideStep(db.Model):
    __tablename__ = 'oper_guide_step'
    gsid = db.Column(db.Integer, autoincrement=True, primary_key=True)
    step_name = db.Column(db.String(30), nullable=False)
    step_desc = db.Column(db.Text)
    actual = db.Column(db.Text)
    judge = db.Column(db.Text)
    display = db.Column(db.Text)
    trigger =  db.Column(db.Text)
    force_done = db.Column(db.Boolean, default=False)
    force_done_user = db.Column(db.Integer, db.ForeignKey('users.uid', ondelete='SET NULL'))
    force_done_time = db.Column(db.DateTime)
    display_order = db.Column(db.Integer)
    guide_system = db.Column(db.Integer, db.ForeignKey('oper_guide_system.gsysid', ondelete='SET NULL'))
    unit = db.Column(db.Integer, db.ForeignKey('unit_system.usid', ondelete='SET NULL'))
    DELETED = db.Column(db.Boolean, default=False)

    # user = db.relationship('User', lazy='subquery')

    def __repr__(self) -> str:
        return '<GuideStep-{} {} {}>'.format(self.gsid, self.step_name, '(DELETED)' if self.DELETED else '')

    def to_json(self, full=True, need_user=True) -> dict:
        json_str = {
            "pid": self.gsid,
            "step_name": self.step_name,
            "step_desc": self.step_desc,
            "actual": self.actual,
            "judge": self.judge,
            "display": self.display,
            "trigger": self.trigger,
            "display_order": self.display_order,
            "force_done": self.force_done,
            "force_done_time": datetime.datetime.timestamp(self.force_done_time) if self.force_done_time else None
        }

        # if full and self.guide_system:
        #     # gsystem, _ = OperGuideSystem.get_guide_sys_by_id(self.guide_system, self.unit, need_steps=False)
        #     gsystem, _ = OperGuideStep.get_guide_sys_by_id(self.guide_system, need_steps=False)
        #     json_str['guide_system'] = gsystem.to_json(full=False) if gsystem else None
        
        if need_user and self.force_done_user:
            user = User.get_by_id(self.force_done_user)
            if user:
            # force_done_user = self.user
            # if force_done_user:
                json_str['force_done_user'] = user.to_json(need_role=False)

        return json_str

    @classmethod
    def create_step(cls, step_name, step_desc, judge, trigger, display, actual, order, guide_system, force_done, user_id, unit):
        with session_maker() as db_session:
            max_order = db_session.query(db.func.max(cls.display_order)).filter(cls.guide_system == guide_system, cls.DELETED == False).first()[0]
            if max_order is None:
                max_order = 0
            if order is None:
                order = max_order + 1
            elif order > max_order + 1:
                return False, '步骤排序超出限制'

            force_done_user = user_id if force_done else None
            force_done_time = datetime.datetime.now() if force_done else None

            new_step = OperGuideStep(step_name=step_name, step_desc=step_desc, judge=judge, trigger=trigger,
                                     display=display, actual=actual, display_order=order, guide_system=guide_system,
                                     unit=unit, DELETED=False, force_done=force_done, force_done_user=force_done_user,
                                     force_done_time=force_done_time)
            
            effected_steps = db_session.query(cls).filter(cls.guide_system == guide_system,
                                                          cls.display_order >= order,
                                                          cls.DELETED == False).all()
            
            for step in effected_steps:
                step.display_order += 1

            db_session.add(new_step)
            return True, ''
    
    @classmethod
    def delete_steps(cls, gsids: list):
        with session_maker() as db_session:
            if len(gsids) == 0:
                return

            target_steps = list()
            for gsid in gsids:
                target_step = db_session.query(cls).get(gsid)
                target_step.DELETED = True
                target_steps.append(target_step)
            
            target_steps = sorted(target_steps, key=lambda x: x.display_order)

            start_order = target_steps[0].display_order
            guide_system_id = target_steps[0].guide_system
            step_need_modify = db_session.query(cls).filter(cls.display_order > start_order,
                                                            cls.DELETED == False,
                                                            cls.guide_system == guide_system_id).all()
            current_order = start_order
            for step in step_need_modify:
                step.display_order = current_order
                current_order += 1

        # for gsid in gsids:
        #     cls.delete_step(gsid)

    @classmethod
    def update_step(cls, gsid, data):
        with session_maker() as db_session:
            if len(data) == 0:
                return

            if 'display_order' in data:
                target_step = db_session.query(cls).get(gsid)

                # 将当前步骤向后移动
                if data['display_order'] > target_step.display_order:
                    effected_steps = db_session.query(cls).filter(cls.guide_system == target_step.guide_system,
                                                                  cls.display_order > target_step.display_order,
                                                                  cls.display_order <= data['display_order']).all()
                    for step in effected_steps:
                        step.display_order -= 1
                
                # 将当前步骤向前移动
                elif data['display_order'] < target_step.display_order:
                    effected_steps = db_session.query(cls).filter(cls.guide_system == target_step.guide_system,
                                                                  cls.display_order >= data['display_order'],
                                                                  cls.display_order < target_step.display_order).all()
                    for step in effected_steps:
                        step.display_order += 1
            
            db_session.query(cls).filter(cls.gsid == gsid, cls.DELETED == False).update(data)
            
    @classmethod
    def get_by_id(cls, gsid, unit):
        with session_maker() as db_session:
            step = db_session.query(cls).filter(cls.gsid == gsid, cls.DELETED == False, cls.unit == unit).first()
            if step:
                db_session.expunge(step)
            return step
    
    @classmethod
    def get_by_name(cls, name):
        with session_maker() as db_session:
            step = db_session.query(cls).filter(cls.step_name == name, cls.DELETED == False).first()
            if step:
                db_session.expunge(step)
            return step
    
    @classmethod
    def get_by_desc(cls, desc):
        with session_maker() as db_session:
            step = db_session.query(cls).filter(cls.step_desc == desc, cls.DELETED == False).first()
            if step:
                db_session.expunge(step)
            return step
    
    @classmethod
    def get_guide_sys_by_id(cls, cid, page=None, size=None, need_steps=True) -> dict:
        '''
        此函数应被OperGuideSystem.get_guide_sys_by_id()代替
        '''
        with session_maker() as db_session:
            guide_sid = db_session.query(SystemConfig.cid).filter(SystemConfig.name == "GUIDE").first()[0]
            target_guide_sys = db_session.query(SystemConfig).filter(SystemConfig.cid == cid, 
                                                                     SystemConfig.parent == guide_sid, 
                                                                     SystemConfig.DELETED == False).first()

            if not target_guide_sys:
                return None, None

            res = {
                'cid': target_guide_sys.cid,
                'name': target_guide_sys.name,
                'alias': target_guide_sys.alias
            }

            total_steps = None
            if need_steps:
                guide_steps = db_session.query(cls).filter(cls.guide_system == res['cid'], cls.DELETED == False).order_by(cls.display_order).paginate(page=page, per_page=size, error_out=False)
                res['steps'] = [s.to_json(full=False) for s in guide_steps.items]
                total_steps = guide_steps.total
            
            return res, total_steps
    
    @classmethod
    def force_to_done_steps(cls, gsids: list, user_id: int, done: bool):
        '''
        将gsid属于gsids列表的操作指导步骤设置为强制完成状态或解除强制完成状态
        Args:
            gsids: 需要操作的步骤id列表
            user_id: 操作用户id
            done: True表示强制完成, False表示解除强制完成
        '''
        with session_maker() as db_session:
            update_data = {
                'force_done_user': user_id,
                'force_done_time': datetime.datetime.now(),
                'force_done': done
            }
            db_session.query(cls).filter(cls.gsid.in_(gsids)).update(update_data)
    
    @classmethod
    def get_all_guide_steps_for_check(cls) -> dict:
        '''
        获取所有需要实时值检查的操作指导系统步骤
        '''
        with session_maker() as db_session:
            all_step_dict = dict()
            all_steps = db_session.query(cls).filter(cls.DELETED == False, cls.force_done == False).all()
            for step in all_steps:
                all_step_dict[step.step_name] = (step.gsid, step.actual, step.judge, step.display, step.trigger,
                                                 step.guide_system, step.unit)
            
            return all_step_dict

    @classmethod
    def search_all(cls, step_name: str, step_desc: str, unit: Union[str, int], guide_system: int, all_unit=False):
        query_list = list()
        if step_name:
            query_list.append(cls.step_name.like(step_name + '%'))
        if step_desc:
            query_list.append(cls.step_desc.like('%' + step_desc + '%'))
        if not all_unit:
            query_list.append(cls.unit == unit)
        
        query_list.append(cls.guide_system == guide_system)
        query_list.append(cls.DELETED.is_(False))
        
        with session_maker() as db_session:
            result = db_session.query(cls).filter(*query_list) \
                               .order_by(cls.display_order).all()
            for res in result:
                db_session.expunge(res)
            return result, len(result)
