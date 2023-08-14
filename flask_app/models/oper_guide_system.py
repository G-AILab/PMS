from typing import Union
from flask_app import db
from flask_app import session_maker
from flask_app.models.unit_system import UnitSystem
from flask_app.models.oper_guide_step import OperGuideStep


class OperGuideSystem(db.Model):
    __tablename__ = 'oper_guide_system'
    gsysid = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(40))
    alias = db.Column(db.String(60))
    force_done = db.Column(db.Boolean, default=False)
    DELETED = db.Column(db.Boolean, default=False)
    unit = db.Column(db.Integer, db.ForeignKey('unit_system.usid', ondelete='SET NULL'))

    def __repr__(self) -> str:
        return '<GuideSystem-{} {} {} {}>'.format(self.gsysid, self.name, self.alias, self.unit)

    def to_json(self) -> dict:
        json_dict = {
            "cid": self.gsysid,
            "name": self.name,
            "alias": self.alias,
            "force_done": self.force_done
        }

        if self.unit is not None:
            json_dict['unit'] = UnitSystem.get_by_id(self.unit).to_json()

        return json_dict
    
    @classmethod
    def create_guide_system(cls, name, alias, unit):
        with session_maker() as db_session:
            new_guide_system = cls(name=name, alias=alias, unit=unit, DELETED=False)
            db_session.add(new_guide_system)

    @classmethod
    def get_all_guide_systems(cls, unit, page=None, size=None):
        with session_maker() as db_session:
            systems = db_session.query(cls).filter(cls.unit == unit, cls.DELETED == False).all()

            for sys in systems:
                db_session.expunge(sys)
            
            return systems, len(systems)
    
    @classmethod
    def get_guide_systems_by_page(cls, unit, page, size):
        with session_maker() as db_session:
            systems = db_session.query(cls).filter(cls.unit == unit, cls.DELETED == False).paginate(page=page, per_page=size, error_out=False)

            for sys in systems.items:
                db_session.expunge(sys)
            
            return systems.items, systems.total
    
    @classmethod
    def get_guide_sys_by_id(cls, gsysid, unit, page=None, size=None, need_steps=True):
        with session_maker(print_close=False) as db_session:
            target_guide_sys = db_session.query(cls).filter(cls.gsysid == gsysid, cls.DELETED == False, cls.unit == unit).first()

            if not target_guide_sys:
                return None, None, 0

            res = {
                'cid': target_guide_sys.gsysid,
                'name': target_guide_sys.name,
                'alias': target_guide_sys.alias,
                'force_done': target_guide_sys.force_done
            }

            total_steps = 0
            steps = None
            if need_steps:
                if page and size:
                    guide_steps = db_session.query(OperGuideStep).filter(OperGuideStep.guide_system == res['cid'],
                                                                        OperGuideStep.DELETED == False)\
                                                                .order_by(OperGuideStep.display_order).paginate(page=page, per_page=size, error_out=False)
                    
                    # for s in guide_steps.items:
                    #     print(s.to_json(full=False))
                    for s in guide_steps.items:
                        db_session.expunge(s)

                    steps = guide_steps.items
                    # res['steps'] = [s.to_json(full=False) for s in guide_steps.items]
                    total_steps = guide_steps.total
                else:
                    guide_steps = db_session.query(OperGuideStep).filter(OperGuideStep.guide_system == res['cid'],
                                                                        OperGuideStep.DELETED == False)\
                                                                .order_by(OperGuideStep.display_order).all()
                    # res['steps'] = list()
                    # for s in guide_steps:
                    #     # res['steps'].append(s.to_json(full=False))
                    #     step_info = {
                    #         "pid": s.gsid,
                    #         "step_name": s.step_name,
                    #         "step_desc": s.step_desc,
                    #         "actual": s.actual,
                    #         "judge": s.judge,
                    #         "display": s.display,
                    #         "trigger": s.trigger,
                    #         "display_order": s.display_order,
                    #         "force_done": s.force_done,
                    #         "force_done_time": s.force_done_time
                    #     }

                        # if s.force_done_user:
                        #     user = User.get_by_id(s.force_done_user)
                        #     step_info['force_done_user'] = user.to_json(full=False)
                        # res['steps'].append(step_info)
                    # print(res['steps'])
                    for s in guide_steps:
                        db_session.expunge(s)
                    steps = guide_steps
                    # res['steps'] = [s.to_json(full=False, need_user=False) for s in guide_steps]
                    total_steps = len(steps)
            
            return res, steps, total_steps
    
    @classmethod
    def update_guide_system(cls, gsysid, data):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.gsysid == gsysid).update(data)
    
    @classmethod
    def force_to_done_system(cls, gsysid: int, done: bool):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.gsysid == gsysid).update({'force_done': done})
    
    @classmethod
    def delete_guide_system(cls, gsysid):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.gsysid == gsysid).update({'DELETED': True})

    @classmethod
    def search_all(cls, sys_name: str, sys_alias: str, unit: Union[str, int], all_unit=False):
        query_list = list()
        
        if sys_name:
            query_list.append(cls.name.like('%' + sys_name + '%'))
        if sys_alias:
            query_list.append(cls.alias.like('%' + sys_alias + '%'))
        if not all_unit:
            query_list.append(cls.unit == unit)
        
        with session_maker() as db_session:
            return_sys = db_session.query(cls).filter(*query_list).all()
            for sys in return_sys:
                db_session.expunge(sys)
            return return_sys, len(return_sys)
