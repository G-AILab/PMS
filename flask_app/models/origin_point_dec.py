from enum import Enum
from typing import List, Dict, Union, Tuple
import json
from sqlalchemy import inspect
from sqlalchemy.dialects.mysql import insert

from flask_app import db
from flask_app import session_maker
from flask_app import flask_app
from flask_app import redis
from flask_app.models.system_config import SystemConfig
from flask_app.models.point_desc import PointDesc
from loguru import logger


class PointType(Enum):
    ORIGINPOINTDESC = 0
    INTERVARIABLE = 1


class OriginPointDesc(db.Model):
    __tablename__ = 'origin_point_desc'
    tag_name = db.Column(db.String(30), nullable=False, primary_key=True)
    describe = db.Column(db.Text)
    unit = db.Column(db.Integer, db.ForeignKey('unit_system.usid', ondelete='SET NULL'))
    point_type = db.Column(db.Integer, default=0)

    def __repr__(self) -> str:
        return '<OriginPointDesc-{}>'.format(self.tag_name)

    def __eq__(self, other):
        return self.tag_name == other.tag_name

    def to_json(self, full=True) -> Dict:
        """修改！返回origin point desc信息
        Args:
            full: True加上system config信息，反之亦然
        Returns:
            dict . origin point desc 的 序列化对象
        """
        json_str = {
            "tag_name": self.tag_name,
            "point_name": self.tag_name,
            "describe": self.describe,
            "point_desc": self.describe,
            "unit": self.unit,
            "point_type": self.point_type
        }
        if full:
            systems = []
            for s in self.systems:
                systems.append(s.to_json(full=False))
            json_str['systems'] = systems
        return json_str

    def to_dict(self) -> Dict:
        return {
            "tag_name": self.tag_name,
            "describe": self.describe,
            "unit": self.unit,
            "point_type": self.point_type if self.point_type is not None else 0
        }

    @classmethod
    def create_origin_point_desc(cls, tag_name: str, describe: str, unit: Union[str, int, None] = None):
        with session_maker() as db_session:
            origin_point_desc = OriginPointDesc(tag_name=tag_name, describe=describe,unit=unit,
                                                point_type=PointType.ORIGINPOINTDESC.value)
            db_session.add(origin_point_desc)
            db_session.commit()
            # refresh 刷新session缓存对象
            db_session.refresh(origin_point_desc)
            # 从会话中去除origin point desc对象
            for s in origin_point_desc.systems:
                db_session.expunge(s)
            db_session.expunge(origin_point_desc)
            return origin_point_desc

    @classmethod
    def add_origin_point(cls, tag_name: str, describe: str, system_names: List[str], unit: str):
        # 未调用，不修改
        """修改！！ origin point desc 与 system config 多对多关系
        多线程、多进程下会发生什么？
        """
        flag = None
        msg = ""
        with session_maker() as db_session:
            if cls.get_by_name(tag_name, unit) is not None:
                return False, "Duplicate entry '{}' for key 'PRIMARY'".format(tag_name)
            origin_point_desc = OriginPointDesc(tag_name=tag_name, describe=describe)
            error_list = list()
            for sys_name in system_names:
                system: SystemConfig = SystemConfig.get_by_name(sys_name, unit)
                if not system or (system.children is not None and system.children != ''):
                    error_list.append(sys_name)
                    continue

                if origin_point_desc not in system.origin_points:
                    system.origin_points.append(origin_point_desc)

            if len(error_list) > 0:
                if len(system_names) == len(error_list):
                    flag = False
                    msg = '系统 {} 找不到'.format(', '.join([str(error) for error in error_list]))
                else:
                    flag = True
                    msg = '系统 {} 找不到'.format(', '.join([str(error) for error in error_list]))
            db_session.add(origin_point_desc)
            db_session.commit()
            # refresh 刷新session缓存对象
            db_session.refresh(origin_point_desc)
            # 从会话中去除origin point desc对象
            db_session.expunge(origin_point_desc)
            if flag is not None:
                return flag, msg
            else:
                return True, origin_point_desc.to_json()

    @classmethod
    def delete_origin_point(cls, tag_name: str, unit: Union[str, int]) -> str:
        """修改！！ 删除数据库中的数据,同时将其从system config中去除，将关联的point desc设置为DELETED
        Args:
            tag_name: tag_name
        Returns:
            params name
        """
        from flask_app.models.inter_variable import InterVariable
        with session_maker() as db_session:
            origin_point = db_session.query(cls).filter(cls.tag_name == tag_name).first()
            if origin_point is None:
                return tag_name
            db_session.query(PointDesc).filter(PointDesc.point_name == tag_name, PointDesc.unit == unit) \
                .update({'DELETED': True})
            
            db_session.query(InterVariable).filter(InterVariable.var_name == tag_name).delete()
            db_session.delete(origin_point)
            db_session.commit()
            return tag_name

    @classmethod
    def delete_origin_points(cls, tag_names: List[str], unit: Union[str, int]):
        from flask_app.models.inter_variable import InterVariable
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.tag_name.in_(tag_names)).delete()
            db_session.query(PointDesc).filter(PointDesc.point_name.in_(tag_names), PointDesc.unit == unit).update(
                {'DELETED': True})
            # 暂不确定中间变量是否要求unit也对应，此时InterVariable内不含unit(但数据库有)
            db_session.query(InterVariable).filter(InterVariable.var_name.in_(tag_names)).delete()
            db_session.commit()

    @classmethod
    def add_systems(cls, tag_name: str, snames: List[str], unit: Union[str, int]) -> str:
        with session_maker() as db_session:
            origin_point = db_session.query(cls).get(tag_name)
            if origin_point is None:
                return "[ERROR] name do not exist"
            err_list = list()
            for sname in snames:
                target_system: SystemConfig = db_session.query(SystemConfig).filter(
                    SystemConfig.name == sname,
                    SystemConfig.DELETED == False,
                    SystemConfig.unit == unit
                ).first()
                if not target_system or (target_system.children is not None and target_system.children != ''):
                    err_list.append('系统 {} 找不到'.format(sname))
                    continue
                if origin_point in target_system.origin_points:
                    err_list.append('系统 {} 已存在'.format(sname))
                    continue
                target_system.origin_points.append(origin_point)
            if len(err_list) > 0:
                return '; '.join(err_list)
            else:
                return "成功"

    @classmethod
    def delete_systems(cls, tag_name: str, sname: str, unit: Union[str, int]) -> str:
        with session_maker() as db_session:
            point = db_session.query(cls).get(tag_name)
            target_system = db_session.query(SystemConfig).filter(SystemConfig.name == sname,
                                                                  SystemConfig.DELETED.is_(False),
                                                                  SystemConfig.unit == unit).first()
            if not target_system:
                return '系统 {} 找不到'.format(sname)
            if point not in target_system.origin_points:
                return '{} 不在当前点的所属系统中'.format(sname)
            target_system.origin_points.remove(point)
            return ''

    @classmethod
    def change_systems(cls, tag_name: str, snames: List[str], unit: Union[str, int]):
        with session_maker() as db_session:
            origin_point = db_session.query(cls).filter(cls.tag_name == tag_name).first()
            if origin_point is None:
                return ""
            systems = db_session.query(SystemConfig).filter(SystemConfig.name.in_(snames), SystemConfig.DELETED.is_(False), SystemConfig.unit == unit).all()
            existed_names = [system.name for system in systems]
            if len(existed_names) > 0:
                origin_point.systems.clear()
                origin_point.systems.extend([system for system in systems if system.name in existed_names])
            error_list = list(set(snames) - set(existed_names))
            if len(error_list) > 0:
                return f"{','.join(error_list)}不存在"
            else:
                return None

    @classmethod
    def get_all_in_unit(cls, unit, page=None, size=None):
        with session_maker() as db_session:
            origin_point_list = list()
            total = 0
            if page and size:
                origin_points = db_session.query(cls).filter(cls.unit == unit).paginate(page=page, per_page=size)
                for origin_point in origin_points.items:
                    for sys in origin_point.systems:
                        db_session.expunge(sys)
                    db_session.expunge(origin_point)
                total = origin_points.total
                origin_point_list = origin_points.items
            else:
                origin_points = db_session.query(cls).filter(cls.unit == unit).all()
                for point in origin_points:
                    for sys in point.systems:
                        db_session.expunge(sys)
                    db_session.expunge(point)
                total = len(origin_points)
                origin_point_list = origin_points
            return origin_point_list, total

    @classmethod
    def get_by_page(cls, page, size, unit):
        selected_systems, total = cls.get_all_in_unit(unit, page, size)
        return selected_systems, total

    @classmethod
    def set_desc(cls, tag_name: str, desc: str, unit: Union[str, int]):
        """更新describe
        Args:
            tag_name: tag name
            desc: describe
            unit: unit
        Returns:
            OriginPointDesc对象
        """
        with session_maker() as db_session:
            origin_point_desc = db_session.query(cls).filter(cls.tag_name == tag_name).update({"describe": desc})
            db_session.query(PointDesc).filter(PointDesc.point_name == tag_name, PointDesc.unit == unit).update({"describe": desc})
            return origin_point_desc

    @classmethod
    def get_by_name(cls, name: str, unit: Union[str, int]):
        with session_maker() as db_session:
            if unit is not  None:
                origin_point_desc = db_session.query(cls).filter(cls.tag_name == name, cls.unit == unit).first()
            else:
                origin_point_desc = db_session.query(cls).filter(cls.tag_name == name).first()
            if not origin_point_desc:
                return None
            if origin_point_desc.systems:
                for system in origin_point_desc.systems:
                    db_session.expunge(system)
            db_session.expunge(origin_point_desc)
            return origin_point_desc

    @classmethod
    def get_origin_points_by_names(cls, names: List[str], unit: Union[str, int]):
        """
        Args:
            names: 原点名称列表
            unit: 机组
        Returns:
            list[OriginPointDesc]:原始点列表.根据点名-精确地(in not like)-批量获取原始点
        """
        with session_maker() as db_session:
            origin_points = db_session.query(cls).filter(cls.tag_name.in_(names), cls.unit == unit).all()
            for origin_point in origin_points:
                if origin_point.systems:
                    for system in origin_point.systems:
                        db_session.expunge(system)
                db_session.expunge(origin_point)
            return origin_points

    @classmethod
    def clear_table(cls, unit):
        # 模型映射  返回字典
        db.reflect(app=flask_app)
        # for table_name in db.metadata.tables:
        # get_engine 获得连接引擎 执行mysql命令
        db.get_engine().execute(f"SET foreign_key_checks = 0")
        db.get_engine().execute(f"DELETE FROM {cls.__tablename__}")
        db.get_engine().execute(f"SET foreign_key_checks = 1")
        return 'ok'

    @classmethod
    def search_all(cls, tag_name: str, point_desc: str, system_name: str, system_alias: str, unit: Union[str, int],
                   page=None, size=None, point_type=[PointType.ORIGINPOINTDESC.value, PointType.INTERVARIABLE.value], all_unit=False):
        # 分页查询
        query_list, has_system = cls.__get_search_all_query_list(tag_name, point_desc, system_name, 
                                                                 system_alias, unit, all_unit=all_unit)
        
        with session_maker() as db_session:
            if has_system:
                filtered_points = db_session.query(cls).join(cls.systems) \
                                            .filter(*query_list, cls.point_type.in_(point_type)) \
                                            .paginate(page=page, per_page=size)
            else:
                filtered_points = db_session.query(cls) \
                                            .filter(*query_list, cls.point_type.in_(point_type)) \
                                            .paginate(page=page, per_page=size)

            for point in filtered_points.items:
                for sys in point.systems:
                    db_session.expunge(sys)
                db_session.expunge(point)
            return filtered_points.items, filtered_points.total

    @classmethod
    def search_all_no_page(cls, tag_name: str, point_desc: str, system_name: str, system_alias: str, unit: Union[str, int], 
                           point_type=[PointType.ORIGINPOINTDESC.value, PointType.INTERVARIABLE.value], all_unit=False):
        query_list, has_system = cls.__get_search_all_query_list(tag_name, point_desc, system_name, 
                                                                 system_alias, unit, all_unit=all_unit)
        
        with session_maker() as db_session:
            if has_system:
                filtered_points = db_session.query(cls).join(cls.systems) \
                                            .filter(*query_list, cls.point_type.in_(point_type)) \
                                            .all()
            else:
                filtered_points = db_session.query(cls) \
                                            .filter(*query_list, cls.point_type.in_(point_type)) \
                                            .all()

            for point in filtered_points:
                for sys in point.systems:
                    db_session.expunge(sys)
                db_session.expunge(point)
            return filtered_points, len(filtered_points)

    @classmethod
    def __get_search_all_query_list(cls, tag_name: str, point_desc: str, system_name: str, 
                                    system_alias: str, unit: Union[str, int], all_unit=False):
        query_list = list()
        has_system = False
        if tag_name:
            query_list.append(cls.tag_name.like('%' + tag_name + '%'))

        if point_desc:
            query_list.append(cls.describe.like('%' + point_desc + '%'))

        if system_name:
            has_system = True
            query_list.append(
                db.and_(SystemConfig.name.like('%' + system_name + '%'), SystemConfig.DELETED == False))

        if system_alias:
            has_system = True
            query_list.append(
                db.and_(SystemConfig.alias.like('%' + system_alias + '%'), SystemConfig.DELETED == False))
        
        if not all_unit:
            query_list.append(cls.unit == unit)
        return query_list, has_system

    @classmethod
    def upsert(cls, points: List):
        if isinstance(points[0], cls):
            points = [{
                "tag_name": point.tag_name,
                "describe": point.describe,
                "unit": point.unit,
            } for point in points]
        with session_maker() as db_session:
            # 批量插入数据
            insert_stmt = insert(cls).values(points)
            # 主键重复时更新指定字段
            stmt = insert_stmt.on_duplicate_key_update({"describe": insert_stmt.inserted.describe})
            db_session.execute(stmt)
            db_session.commit()

    @classmethod
    def upsert_all(cls, records: list):
        # tag_name: str, describe: str, unit: Union[str, int, None] = None
        # 获取所有主键属性名称列表
        primary_keys = [col.name for col in inspect(cls).primary_key]
        # 获取全部字段名称列表
        total_fields = inspect(cls).c.keys()
        # 需要更新的字段名称列表
        update_keys = [key for key in total_fields if key not in primary_keys]
        
        if isinstance(records[0], cls):
            data = [{
                "tag_name": record.tag_name,
                "describe": record.describe,
                "unit": record.unit,
                "point_type": record.point_type if record.point_type is not None else PointType.ORIGINPOINTDESC.value
            } for record in records]
        else:
            return False, "请传入相应的实体对象列表."
        insert_stmt = insert(cls).values(data)
        
        # 主键已存在时需要更新的列，其实就是除主键以外的全部列
        update_columns = {x.name: x for x in insert_stmt.inserted if x.name in update_keys}
        # 当遇上关系表这样的多对多并且全部字段组成复合主键时，不存在则插入，存在则更新全部字段
        if not len(update_columns):
            update_columns = {x.name: x for x in insert_stmt.inserted if x.name in total_fields}
        
        upsert_stmt = insert_stmt.on_duplicate_key_update(**update_columns)
        with session_maker() as db_session:
            db_session.execute(upsert_stmt)
            db_session.commit()
        return True, "upsert 成功."

    @classmethod
    def get_point_and_variable(cls):
        """
            用于将原始点名写入Reids，获取所有点包括中间变量
        """
        with session_maker() as db_session:
            names = db_session.query(cls.tag_name, cls.point_type).all()
            origin_points = [item[0] for item in names if item[1] == PointType.ORIGINPOINTDESC.value]
            from flask_app.models.inter_variable import InterVariable
            inter_variables = db_session.query(InterVariable.var_name, InterVariable.var_value).all()
            return origin_points, dict(inter_variables)

    @classmethod
    def get_have_point_desc_points(cls, tag_names: List[str]):
        with session_maker() as db_session:
            result = db_session.query(PointDesc.point_name).filter(PointDesc.point_name.in_(tag_names),
                                                                   PointDesc.DELETED.is_(False)).all()
            return [item[0] for item in result]

    @classmethod
    def get_point_descs_by_name(cls, tag_names: List[str]):
        with session_maker() as db_session:
            result = db_session.query(cls.tag_name, cls.describe).filter(cls.tag_name.in_(tag_names)).all()
            res = dict()
            for tag, desc in result:
                res[tag] = desc
            return res, len(result)


def write_origin_points_to_redis(origin_point=False, inter_variable=False):
    """
    将原始点名写入redis
    """
    origin_points, inter_variables = OriginPointDesc.get_point_and_variable()

    origin_point_names = "origin_point_names"
    inter_variables_names = "inter_variable_names"
    auto = "all_points"
    origin_point_flag = "origin_point_flag"
    inter_variable_flag = "inter_variable_flag"

    redis.write(origin_point_names, ",".join(origin_points))
    redis.write(inter_variables_names, json.dumps(inter_variables))
    redis.write(auto, ",".join([*origin_points, *(list(inter_variables.keys()))]))

    if origin_point:
        redis.write(origin_point_flag, "True")
    if inter_variable:
        redis.write(inter_variable_flag, "True")
    redis.persist(origin_point_names)
    redis.persist(inter_variables_names)
    redis.persist(auto)
    redis.persist(origin_point_flag)
    redis.persist(inter_variable_flag)
