from genericpath import exists
from typing import List, Union

from flask_app import db, session_maker
from flask_app.models.origin_point_dec import OriginPointDesc, PointType
from flask_app.models.origin_point_system_config import OriginPointSystemConfig
from flask_app.models.relation_map import origin_point_system_config
from flask_app.models.system_config import SystemConfig
from sqlalchemy import select
from sqlalchemy.sql import exists
from itertools import groupby


class InterVariable(db.Model):
    __tablename__ = 'inter_variable'
    vid = db.Column(db.Integer, autoincrement=True, primary_key=True)
    var_name = db.Column(db.String(30), nullable=False)
    var_value = db.Column(db.Text)
    remark = db.Column(db.Text)
    DELETED = db.Column(db.Boolean, default=False)
    status = db.Column(db.Integer)      #历史数据填充状态 -1:未填充 0：填充中 1：填充完成 2：填充失败
    process = db.Column(db.Numeric(5,2)) #历史数据填充进度

    def to_json(self, eval_value:bool =False):
        if self.status is not None:
            status = self.status
        else:
            status = -1
        if self.process is not None:
            process = self.process
        else:
            process = 100.00
        json_dict = {
            'vid': self.vid,
            'var_name': self.var_name,
            'var_value': self.var_value,
            'remark': self.remark,
            'status': status,
            'process': process
        }
        if bool(eval_value) is True:
            from  flask_app.util.rpc.point_desc  import  inter_var_eval_val_or_error
            json_dict['eval_value'] = inter_var_eval_val_or_error(json_dict['var_value'])   
        return json_dict


    def to_dict(self) -> dict:
        return {
            'var_name': self.var_name,
            'var_value': self.var_value,
            'remark': self.remark,
            # 'DELETED': self.DELETED,
            # 'status': self.status,
            # 'process': self.process
        }

    @classmethod
    def get_all(cls):
        '''
        获取所有unit的所有中间变量
        '''
        with session_maker() as db_session:
            all_vars = db_session.query(cls).filter(cls.DELETED.is_(False)).all()
            for var in all_vars:
                db_session.expunge(var)
        return all_vars, len(all_vars)

    @classmethod
    def get_unit_all(cls, unit: Union[str, int]):
        """
        获取相应unit的全部中间变量
        """
        with session_maker() as db_session:
            sco = db_session.query(OriginPointDesc) \
                            .where(OriginPointDesc.unit == unit) \
                            .where(OriginPointDesc.tag_name == cls.var_name) \
                            .exists()
            all_vars = db_session.query(cls).filter(cls.DELETED.is_(False), sco).all()
            for var in all_vars:
                db_session.expunge(var)
        return all_vars, len(all_vars)

    @classmethod
    def get_by_page(cls, unit: Union[str, int], page=None, size=None):
        with session_maker() as db_session:
            sco = db_session.query(OriginPointDesc) \
                            .where(OriginPointDesc.unit == unit) \
                            .where(OriginPointDesc.tag_name == cls.var_name) \
                            .exists()
            page_vars = db_session.query(cls) \
                                  .filter(cls.DELETED == False, sco) \
                                  .paginate(page=page, per_page=size, error_out=False)
            for var in page_vars.items:
                db_session.expunge(var)
        return page_vars.items, page_vars.total

    # @classmethod
    # def __get_unit_exists(cls, unit, db_session):
    #     sco = db_session.query(OriginPointDesc) \
    #                     .where(OriginPointDesc.unit == unit) \
    #                     .where(OriginPointDesc.tag_name == cls.var_name) \
    #                     .exists()
    #     return sco

    @classmethod
    def create(cls, vname, vvalue, remark, status, unit, process=0.00):
        with session_maker() as db_session:
            new_var = InterVariable(var_name=vname, var_value=vvalue, remark=remark, status=status, process = process, DELETED=False)
            origin_point = db_session.query(OriginPointDesc).filter(OriginPointDesc.tag_name == vname).first()
            if origin_point is None:
                origin_point = OriginPointDesc(tag_name=vname, describe=remark, unit=unit,
                                               point_type=PointType.INTERVARIABLE.value)
                db_session.add(origin_point)
                db_session.add(new_var)
                db_session.flush()
                db_session.expunge(origin_point)
                vid = new_var.vid
                return vid, "创建成功"
            else:
                return False, "存在相同名称原始点"

    @classmethod
    def update(cls, vid, unit, data):
        with session_maker() as db_session:
            target = db_session.query(cls).filter(cls.vid == vid, cls.DELETED.is_(False)).first()
            if not target:
                return False, '找不到指定中间变量'
            # 不更新中间点名称和id
            data.pop("vid", None)
            data.pop('var_name', None)

            # 同时更新原始点描述
            if "remark" in data:
                OriginPointDesc.set_desc(target.var_name, data['remark'], unit)
            db_session.query(cls).filter(cls.vid == vid).update(data)
            return True, ''

    @classmethod
    def delete(cls, vid, unit):
        with session_maker() as db_session:
            target = db_session.query(cls).filter(cls.vid == vid, cls.DELETED.is_(False)).first()

            if not target:
                return False, '找不到指定的中间变量'

            target.DELETED = True
            OriginPointDesc.delete_origin_point(target.var_name, unit)
            return True, ''

    @classmethod
    def get_by_id(cls, vid):
        with session_maker() as db_session:
            inter_var = db_session.query(cls).filter(cls.vid == vid, cls.DELETED.is_(False)).first()
            if not inter_var:
                return None
            db_session.expunge(inter_var)
            return inter_var

    @classmethod
    def get_by_name(cls, vname, unit: Union[str, int]):
        with session_maker() as db_session:
            sco = db_session.query(OriginPointDesc) \
                            .where(OriginPointDesc.unit == unit) \
                            .where(OriginPointDesc.tag_name == cls.var_name) \
                            .exists()
            inter_var = db_session.query(cls) \
                                  .filter(cls.var_name == vname, cls.DELETED.is_(False), sco) \
                                  .first()
            if not inter_var:
                return None
            db_session.expunge(inter_var)
            return inter_var

    @classmethod
    def add_origin_points_info_to_inter_variable(cls, inter_variables: List, eval_value:bool = False):
        result_json = []
        with session_maker() as db_session:
            inter_variable_names = [f'{inter_variable.var_name}' for inter_variable in inter_variables]

            # 通过select 在传入参数范围内的数据
            s = select([origin_point_system_config.columns.origin_point,
                        origin_point_system_config.columns.system_config]).where(
                origin_point_system_config.columns.origin_point.in_(inter_variable_names))
            cursor = db_session.execute(s)
            # 非常蠢的一种方法
            # name_cid = { key:[i[1] for i in value] for key,value in groupby(cursor.fetchall(), lambda x: x[0])}
            # 建立中间变量所属系统的映射关系
            result = cursor.fetchall()
            name_cid = {}
            for item in result:
                inter_variable_name = item[0]
                cid = item[1]
                name_cid[inter_variable_name] = [*name_cid.get(inter_variable_name, []), cid]

            # 在execute之后，session自动commit了，session对象进入了Detached状态，导致无法通过orm进行选择
            s2 = select([SystemConfig.cid, SystemConfig.name, SystemConfig.alias]).where(
                SystemConfig.cid.in_([item[1] for item in result]))
            cursor2 = db_session.execute(s2)
            result2 = cursor2.fetchall()
            # 获取cid和systemconfig的映射关系
            cid_info = {system[0]: {
                "cid": system[0],
                "name": system[1],
                "alias": system[2]
            } for system in result2}

            for inter_variable in inter_variables:
                json = inter_variable.to_json(eval_value=bool(eval_value))
                var_name = inter_variable.var_name
                json["systems"] = []
                if var_name in name_cid:
                    for cid in name_cid[var_name]:
                        json['systems'] = [*json["systems"], cid_info[cid]]
                result_json.append(json)
                
            return result_json

    @classmethod
    def multi_search(cls, var_name, var_value, remark, system, system_alias, unit, page=None, size=None,eval_value=False):
        with session_maker() as db_session:
            if var_value is not None:
                inter_variables = db_session.query(cls).filter(cls.var_value.like('%' + var_value + '%')).all()
            else:
                inter_variables = []
            # 必须，将inter从session中释放，避免选择出origin_point后session关闭导致先选择出的inter_variable被销毁无法再次访问
            for inter in inter_variables:
                db_session.expunge(inter)
            origin_points, _ = OriginPointDesc.search_all(var_name, remark, system, system_alias, unit, page, size, point_type=[PointType.INTERVARIABLE.value])
            tag_names = [origin_point.tag_name for origin_point in origin_points]
            other_inter_variables = []
            other_inter_variables = db_session.query(cls).filter(cls.var_name.in_(tag_names)).all()
            result = [*inter_variables, *other_inter_variables]
            return InterVariable.add_origin_points_info_to_inter_variable(inter_variables=result,eval_value=eval_value)

    @classmethod
    def search_all(cls, var_name: str, var_value: str, remark: str, system_name: str, 
                   system_alias: str, unit: Union[str, int], page=None, size=None, all_unit: bool=False):
        with session_maker() as db_session:
            
            # 临时设定默认值与sqlalchemy一致
            page = page if page else 1
            size = size if size else 20
            
            inter_query_list, sco = cls.__get_search_all_query_list(var_name, var_value, remark, system_name, 
                                                                    system_alias, unit, db_session, all_unit=all_unit)
            
            # sco = (
            #     select(OriginPointDesc.tag_name, OriginPointDesc.unit, SystemConfig.name, SystemConfig.alias).
            #     where(cls.var_name == OriginPointDesc.tag_name, OriginPointDesc.unit == unit, SystemConfig.name.like('%' + system_name + '%')).
            #     exists()
            # )
            
            # 测试用
            # sco = db_session.query(OriginPointDesc, OriginPointSystemConfig, SystemConfig) \
            #                 .where(OriginPointDesc.tag_name == OriginPointSystemConfig.origin_point, SystemConfig.cid == OriginPointSystemConfig.system_config) \
            #                 .where(OriginPointDesc.unit == unit) \
            #                 .where(SystemConfig.name.like('%' + system_name + '%')) \
            #                 .where(cls.var_name == OriginPointDesc.tag_name).exists()
            
            # inter_variables = db_session.query(cls) \
            #                             .filter(*inter_query_list, sco)
                                        
            # print(inter_variables)
            # inter_variables = inter_variables.paginate(page=page, per_page=size)
            
            inter_variables = db_session.query(cls).filter(*inter_query_list, sco) \
                                        .paginate(page=page, per_page=size)
            # 两次查询之间需要释放
            for inter in inter_variables.items:
                db_session.expunge(inter)
            # 查系统
            for var in inter_variables.items:
                query_list = [OriginPointSystemConfig.origin_point == var.var_name, OriginPointSystemConfig.system_config == SystemConfig.cid]
                systems = db_session.query(SystemConfig) \
                                    .filter(*query_list).all()
                # print(var.var_name)
                var.systems = ' '.join([sys.name for sys in systems])
                for sys in systems:
                    db_session.expunge(sys)
            return inter_variables.items, inter_variables.total
        
    @classmethod
    def search_all_no_page(cls, var_name: str, var_value: str, remark: str, system_name: str, 
                           system_alias: str, unit: Union[str, int], all_unit: bool=False):
        with session_maker() as db_session:
            inter_query_list, sco = cls.__get_search_all_query_list(var_name, var_value, remark, system_name, 
                                                                    system_alias, unit, db_session, all_unit=all_unit)
            inter_variables = db_session.query(cls) \
                                        .filter(*inter_query_list, sco) \
                                        .all()
            # 两次查询之间需要释放
            for inter in inter_variables:
                db_session.expunge(inter)
            # 查系统
            for var in inter_variables:
                query_list = [OriginPointSystemConfig.origin_point == var.var_name, OriginPointSystemConfig.system_config == SystemConfig.cid]
                systems = db_session.query(SystemConfig) \
                                    .filter(*query_list).all()
                # print(var.var_name)
                var.systems = ' '.join([sys.name for sys in systems])
                for sys in systems:
                    db_session.expunge(sys)
            return inter_variables, len(inter_variables)
    
    @classmethod
    def __get_search_all_query_list(cls, var_name: str, var_value: str, remark: str, system_name: str, 
                                    system_alias: str, unit: Union[str, int], db_session, all_unit: bool=False):
        # 设置inter表的查询条件
        inter_query_list = list()
        if var_name:
            inter_query_list.append(cls.var_name.like('%' + var_name + '%'))
        if var_value:
            inter_query_list.append(cls.var_value.like('%' + var_value + '%'))
        if remark:
            inter_query_list.append(cls.remark.like('%' + remark + '%'))
        
        # 如果有查询系统要求，则exists子句中就需要联查origin、system、origin_system三表，否则exists只需查origin表
        if system_name or system_alias:
            sco = db_session.query(OriginPointDesc, OriginPointSystemConfig, SystemConfig) \
                            .where(OriginPointDesc.tag_name == OriginPointSystemConfig.origin_point, SystemConfig.cid == OriginPointSystemConfig.system_config)
        else:
            sco = db_session.query(OriginPointDesc)
        
        if not all_unit:
            sco = sco.where(OriginPointDesc.unit == unit)
        if system_name:
            sco = sco.where(SystemConfig.name.like('%' + system_name + '%'))
        if system_alias:
            sco = sco.where(SystemConfig.alias.like('%' + system_alias + '%'))
        
        sco = sco.where(cls.var_name == OriginPointDesc.tag_name).exists()
        
        return inter_query_list, sco