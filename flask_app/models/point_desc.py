from enum import IntEnum
from typing import Any, Union, List
from flask_app import db, session_maker, flask_app, redis
from flask_app.models.origin_point_system_config import OriginPointSystemConfig
from flask_app.models.system_config import SystemConfig
from flask_app.models.unit_system import UnitSystem
class ReminderErrorStatus(int): # python enum 支持很差(json encoder 有多方不兼容的问题)，不实用enum，直接使用int，int 为了使得该类 Json serializable
    NORMAL = 0 
    ERROR = 1  
    # RECOVER = 2 # 从错误自动变回了正常则为Recover


class PointDesc(db.Model):
    __tablename__ = 'point_desc'
    pid = db.Column(db.Integer, autoincrement=True, primary_key=True)
    point_name = db.Column(db.String(30), nullable=False)
    describe = db.Column(db.Text)
    actual = db.Column(db.Text)
    expect = db.Column(db.Text)
    offset = db.Column(db.Text)
    upper_limit = db.Column(db.Text)
    lower_limit = db.Column(db.Text)
    switch = db.Column(db.Text)
    variance_duration = db.Column(db.Text)
    variance_gate = db.Column(db.Text)
    show_upper = db.Column(db.Float)
    show_lower = db.Column(db.Float)
    display_order = db.Column(db.Integer)
    unit = db.Column(db.Integer, db.ForeignKey('unit_system.usid', ondelete='SET NULL'))
    DELETED = db.Column(db.Boolean, default=False)
    all_status = db.Column(db.JSON)  # {'switch': '', 'lower': NORMAL,'upper':, warnings_lists:[]}
    first_warning_list = db.Column(db.JSON)  # {'switch': 'warning', 'lower': NORMAL,'upper':, warnings_lists:[]}
    current_warning_list = db.Column(db.JSON)  # {'switch': '', 'lower': NORMAL,'upper':, warnings_lists:[]}

    def __repr__(self) -> str:
        return '<Point-{} {}>'.format(self.pid, self.point_name)

    def __eq__(self, other):
        return self.point_name == other.point_name

    def to_json_with_value(self, full=True) -> dict:
        from  flask_app.util.rpc.point_desc  import  point_check_filter_val_or_error,point_check_eval_val_or_error, point_check_eval_offset_or_error
        p = self.to_json(full=full)
        # p['actual_value'] = point_check_eval_val_or_error(self.actual)
        # p['expect_value'] = point_check_eval_val_or_error(self.expect)
        # p['offset_value'] = point_check_eval_offset_or_error(self.offset)
        # p['upper_limit_value'] = point_check_eval_val_or_error(self.upper_limit)
        # p['lower_limit_value'] = point_check_eval_val_or_error(self.lower_limit)
        # p['trigger_tag_value'] = point_check_eval_val_or_error(self.switch)
        # p['variance_gate_value'] = point_check_eval_val_or_error(self.variance_gate)
        return p
    
    def to_json(self, full=True) -> dict:
        json_str = {
            "pid": self.pid,
            "point_name": self.point_name,
            "describe": self.describe,
            "actual": self.actual,
            "expect": self.expect,
            "offset": self.offset,
            "upper_limit": self.upper_limit,
            "lower_limit": self.lower_limit,
            "trigger_tag": self.switch,
            "variance_duration": self.variance_duration,
            "variance_gate": self.variance_gate,
            "show_upper": self.show_upper,
            "show_lower": self.show_lower,
            "order": self.display_order,
            "all_status": self.all_status,
            'first_warning_list': self.first_warning_list,
            'current_warning_list':self.current_warning_list,
            # 'systems': self.systems
        }

        if self.unit:
            json_str['unit'] = UnitSystem.get_by_id(self.unit).to_json()

        if full:
            from flask_app.models.origin_point_dec import OriginPointDesc
            origin_point = OriginPointDesc.get_by_name(self.point_name, self.unit)
            if origin_point:
                systems = origin_point.systems
                systems_str = []
                for system in systems:
                    systems_str.append(system.to_json(full=False))
                json_str['systems'] = systems_str
        return json_str

    @classmethod
    def create_point(cls, point_name, describe, expect, offset, upper_limit, lower_limit, switch, unit, v_duration=None,
                     v_gate=None, show_upper=None, show_lower=None, actual=None, order=None):
        """修改！！ 校验point name 是否在origin point desc的tag_name的集合中
        """
        with session_maker() as db_session:
            # try:
            #     from flask_app.models.origin_point_dec import OriginPointDesc
            #     origin_point = OriginPointDesc.get_by_name(point_name, unit)
            #     if origin_point is None:
            #         print("[ERROR] point name not found")
            #         return False, "point name not found. OriginPointDesc not found"
            # except Exception as e:
            #     print(f"Can't import OriginPointDesc model, skip point_name check.Exception is :{e}")

            point_desc = PointDesc(point_name=point_name, describe=describe, expect=expect, offset=offset,
                                   upper_limit=upper_limit, lower_limit=lower_limit, switch=switch,
                                   variance_duration=v_duration, variance_gate=v_gate, show_upper=show_upper,
                                   show_lower=show_lower, actual=actual, display_order=order, unit=unit, DELETED=False)
            db_session.add(point_desc)
            db_session.commit()
            db_session.refresh(point_desc)
            db_session.expunge(point_desc)
            return True, point_desc

    @classmethod
    def check_point_name_list(cls, point_names):
        with session_maker() as db_session:
            try:
                from flask_app.models.origin_point_dec import OriginPointDesc
            except Exception as e:
                print("[ERROR] PointDesc function check_point_name_list error , can't import OriginPointDesc")
                print(f"[ERROR] exception is {e}")
                return point_names
            condition = [OriginPointDesc.tag_name.in_(point_names)]
            valid_point_names = db_session.query(OriginPointDesc.tag_name).filter(*condition).all()
            valid_point_names = [item[0] for item in valid_point_names]
            return valid_point_names

    @classmethod
    def delete_point(cls, pid):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.pid == pid).update({'DELETED': True})
            return pid

    @classmethod
    def delete_points(cls, pids: list):
        with session_maker() as db_session:
            for pid in pids:
                db_session.query(cls).filter(cls.pid == pid).update({'DELETED': True})

    @classmethod
    def delete_points_by_origin_point_tag_name(cls, tag_name: str):
        """new function. 根据origin point 的desc 删除point desc
        Args:
            tag_name: a str within the scope of OriginPointDesc tag_name sets.
        Returns:
            None
        """
        with session_maker() as db_session:
            points = db_session.query(cls).filter(cls.point_name == tag_name).all()
            for point in points:
                db_session.query(cls).filter(cls.pid == point.pid).update({'DELETED': True})
                db_session.refresh(point)
                db_session.expunge(point)

    @classmethod
    def delete_all(cls):
        with session_maker() as db_session:
            db_session.query(cls).delete(synchronize_session=False)
            db_session.commit()

    @classmethod
    def update_point_warnings(cls,point_warnings_list):
        with session_maker() as db_session:
            for point_warnings in point_warnings_list:
                pid = point_warnings['pid']
                all_status = point_warnings['all_status']
                current_warning_list = point_warnings['warnings']
                first_warning_list = point_warnings['first_warning_list']
                data =  {'all_status':all_status, 'current_warning_list':current_warning_list,'first_warning_list':first_warning_list}
                db_session.query(cls).filter(cls.pid == pid).update(data)
            return True, "update success."


    @classmethod
    def update_point_by_name(cls, point_name, data, unit):
        """
        没有考虑describe的一致性问题
        """
        with session_maker() as db_session:
            if len(data) == 0:
                return False

            common_data = dict()
            for key in data:
                if key == "point_name":
                    continue
                if data[key] is not None:
                    common_data[key] = data[key]

            db_session.query(cls).filter(cls.point_name == point_name).update(common_data)
            return True, "update success."
    
    @classmethod
    def update_point(cls, pid, data, unit):
        """
        没有考虑describe的一致性问题
        """
        with session_maker() as db_session:
            if len(data) == 0:
                return False

            common_data = dict()
            for key in data:
                if key == "point_name":
                    continue
                if data[key] is not None:
                    common_data[key] = data[key]

            db_session.query(cls).filter(cls.pid == pid).update(common_data)
            return True, "update success."

    @classmethod
    def get_all_in_unit(cls, unit, page=None, size=None):
        # print(f"{unit} page:{page} size:{size}")
        with session_maker() as db_session:
            if page and size:
                point_descs = db_session.query(cls).filter(cls.unit == unit, cls.DELETED.is_(False)).paginate(page=page, per_page=size, error_out=False)
                for point in point_descs.items:
                    db_session.expunge(point)
                all_points = point_descs.items
                total = point_descs.total
            else:
                all_points = db_session.query(cls).filter(cls.unit == unit, cls.DELETED.is_(False)).all()
                total = 0
                for point in all_points:
                    db_session.expunge(point)
                    total += 1
            return all_points, total

    @classmethod
    def get_by_id(cls, pid, unit) -> 'PointDesc':
        with session_maker() as db_session:
            point_desc = db_session.query(cls).filter(cls.pid == pid, cls.unit == unit, cls.DELETED.is_(False)).first()
            if point_desc:
                db_session.expunge(point_desc)
            return point_desc

    @classmethod
    def get_by_name(cls, name, unit):
        with session_maker() as db_session:
            point_desc = db_session.query(cls).filter(cls.point_name == name, cls.unit == unit, cls.DELETED.is_(False)).first()
            if point_desc:
                db_session.expunge(point_desc)
                systems = db_session.query(SystemConfig) \
                                .filter(OriginPointSystemConfig.origin_point == name, SystemConfig.cid == OriginPointSystemConfig.system_config) \
                                .all()
                if systems:
                    point_desc.systems = systems
                    for sys in systems:
                        db_session.expunge(sys)
            return point_desc

    @classmethod
    def get_points_by_names(cls, names) -> list:
        '''
        根据多个点英文名获取点对象
        '''
        with session_maker() as db_session:
            points = db_session.query(cls).filter(cls.point_name.in_(names), cls.DELETED.is_(False)).all()
            for p in points:
                db_session.expunge(p)
            return points

    @classmethod
    def get_by_page(cls, page, size, unit):
        selected_points, total = cls.get_all_in_unit(unit, page, size)
        return selected_points, total

    @classmethod
    def search_all(cls, point_name: str, point_desc: str, system_name: str, system_alias: str, unit: Union[str, int],
                   page=None, size=None, all_unit=False):
        with session_maker() as db_session:
            try:
                origin_point_desc_names, point_desc_query__condition_list = cls.__get_search_all_query_list(
                    point_name, point_desc, system_name, system_alias, unit, db_session, all_unit=all_unit
                )
                
                filtered_points = db_session.query(cls) \
                                            .filter(*point_desc_query__condition_list,
                                                    cls.point_name.in_(origin_point_desc_names),
                                                    cls.DELETED.is_(False)) \
                                            .paginate(page=page, per_page=size, error_out=False)
                for point in filtered_points.items:
                    db_session.expunge(point)

                return filtered_points.items, filtered_points.total
            except Exception as e:
                print(e)
                return []
            # try:
            #     from flask_app.models.origin_point_dec import OriginPointDesc
            # except Exception as e:
            #     print(e)
            #     return []

            # # point_name , system_name,system_alias,unit
            # origin_point_condition = list()
            # has_system = False
            # if point_name:
            #     origin_point_condition.append(OriginPointDesc.tag_name.like('%' + point_name + '%'))

            # if system_name:
            #     has_system = True
            #     origin_point_condition.append(db.and_(SystemConfig.name.like('%' + system_name + '%'), SystemConfig.DELETED.is_(False)))

            # if system_alias:
            #     has_system = True
            #     origin_point_condition.append(db.and_(SystemConfig.alias.like('%' + system_alias + '%'), SystemConfig.DELETED.is_(False)))

            # if has_system:
            #     origin_points = db_session.query(OriginPointDesc) \
            #         .join(OriginPointDesc.systems) \
            #         .filter(*origin_point_condition) \
            #         .all()
            # else:
            #     origin_points = db_session.query(OriginPointDesc).filter(*origin_point_condition).all()
            # origin_point_desc_names = [item.tag_name for item in origin_points]
            # # print(origin_point_desc_names)
            # point_desc_query__condition_list = list()
            # if point_desc:
            #     point_desc_query__condition_list.append(cls.describe.like('%' + point_desc + '%'))

            # # 指定是否查询特定机组
            # if not all_unit:
            #     point_desc_query__condition_list.append(cls.unit == unit)

            # with session_maker() as db_session:
            #     filtered_points = db_session.query(cls).filter(*point_desc_query__condition_list,
            #                                                    cls.point_name.in_(origin_point_desc_names),
            #                                                 #    cls.unit == unit,
            #                                                    cls.DELETED.is_(False)).paginate(page, size, error_out=False)
            #     for point in filtered_points.items:
            #         db_session.expunge(point)

            #     return filtered_points.items, filtered_points.total

    @classmethod
    def search_all_no_page(cls, point_name: str, point_desc: str, system_name: str, 
                           system_alias: str, unit: Union[str, int], all_unit=False):
        with session_maker() as db_session:
            try:
                origin_point_desc_names, point_desc_query__condition_list = cls.__get_search_all_query_list(
                    point_name, point_desc, system_name, system_alias, unit, db_session, all_unit=all_unit
                )
                
                filtered_points = db_session.query(cls) \
                                            .filter(*point_desc_query__condition_list,
                                                    cls.point_name.in_(origin_point_desc_names),
                                                    cls.DELETED.is_(False)) \
                                            .all()
                for point in filtered_points:
                    db_session.expunge(point)
                    
                for point in filtered_points:
                    query_list = [OriginPointSystemConfig.origin_point == point.point_name, OriginPointSystemConfig.system_config == SystemConfig.cid]
                    systems = db_session.query(SystemConfig) \
                                        .filter(*query_list).all()
                    point.systems = ' '.join([sys.name for sys in systems])
                    for sys in systems:
                        db_session.expunge(sys)

                return filtered_points, len(filtered_points)
            except Exception as e:
                print(e)
                return []
    
    @classmethod
    def __get_search_all_query_list(cls, point_name: str, point_desc: str, system_name: str, system_alias: str, 
                                    unit: Union[str, int], db_session, all_unit=False):
        from flask_app.models.origin_point_dec import OriginPointDesc
        # point_name , system_name,system_alias,unit
        origin_point_condition = list()
        has_system = False
        if point_name:
            origin_point_condition.append(OriginPointDesc.tag_name.like('%' + point_name + '%'))

        if system_name:
            has_system = True
            origin_point_condition.append(db.and_(SystemConfig.name.like('%' + system_name + '%'), SystemConfig.DELETED.is_(False)))

        if system_alias:
            has_system = True
            origin_point_condition.append(db.and_(SystemConfig.alias.like('%' + system_alias + '%'), SystemConfig.DELETED.is_(False)))

        if has_system:
            origin_points = db_session.query(OriginPointDesc) \
                .join(OriginPointDesc.systems) \
                .filter(*origin_point_condition) \
                .all()
        else:
            origin_points = db_session.query(OriginPointDesc).filter(*origin_point_condition).all()
        origin_point_desc_names = [item.tag_name for item in origin_points]
        # 每次查询完毕后释放
        for point in origin_points:
            db_session.expunge(point)
        
        point_desc_query__condition_list = list()
        if point_desc:
            point_desc_query__condition_list.append(cls.describe.like('%' + point_desc + '%'))

        # 指定是否查询特定机组
        if not all_unit:
            point_desc_query__condition_list.append(cls.unit == unit)
        return origin_point_desc_names, point_desc_query__condition_list

    @classmethod
    def clear_table(cls, unit):
        # 模型映射  返回字典
        db.reflect(app=flask_app)
        # for table_name in db.metadata.tables:
        # get_engine 获得连接引擎 执行mysql命令
        db.get_engine().execute("SET foreign_key_checks = 0")
        db.get_engine().execute(f"DELETE FROM {cls.__tablename__} WHERE unit={unit}")
        db.get_engine().execute("SET foreign_key_checks = 1")
        return 'ok'

    @classmethod
    def get_all_limits(cls):
        '''
        获取所有unit所有点的预警规则项
        '''
        with session_maker() as db_session:
            point_limits = db_session.query(cls.pid, cls.point_name, cls.describe, cls.actual, cls.switch, cls.expect,
                                            cls.offset, cls.upper_limit, cls.lower_limit, cls.variance_duration, cls.variance_gate,
                                            cls.unit, cls.all_status, cls.first_warning_list, cls.current_warning_list) \
                .filter(cls.DELETED.is_(False)).all()
            return point_limits

    @classmethod
    def get_belong_systems(cls, points: List):
        from flask_app.models.origin_point_dec import OriginPointDesc
        tag_names = [point.point_name for point in points]
        result = []
        with session_maker() as db_session:
            origin_points = db_session.query(OriginPointDesc).filter(OriginPointDesc.tag_name.in_(tag_names)).all()
            map = {origin_point.tag_name: origin_points for origin_point in origin_points}
            for point in points:
                point_info = point.to_json()
                name = point.point_name
                system_info = map[name].to_json()['systems'] if name in map else {}
                result.append({**point_info, **system_info})
            return result

    @classmethod
    def update_all_status(cls, point_name, all_status):
        from flask_app.models.origin_point_dec import OriginPointDesc
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.point_name == point_name).update({'all_status': all_status})
        return True
    

def read_cold_from_redis(key: str, unit: Union[str, int]):
    import json
    data = redis.read(key)
    if not data:
        return False, {}
    else:
        data = json.loads(data)
        unit = str(unit)
        if unit not in data.keys():
            return True, f"no data in this unit: {unit}"
        for pname in list(data[unit]):
            val = data[unit][pname]
            if not val:
                del data[unit][pname]
        return True, data[unit]