from typing import Dict, List, Union

from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import insert

from flask_app import db
from flask_app import session_maker
from flask_app import flask_app
from flask_app.models.unit_system import UnitSystem


class SystemConfig(db.Model):
    __tablename__ = 'system_config'
    cid = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(40), nullable=False)
    parent = db.Column(db.Integer, db.ForeignKey('system_config.cid', ondelete='SET NULL'))
    alias = db.Column(db.String(30))
    children = db.Column(db.Text)
    DELETED = db.Column(db.Boolean, default=False)
    unit = db.Column(db.Integer, db.ForeignKey('unit_system.usid', ondelete='SET NULL'))
    origin_points = relationship('OriginPointDesc', backref=db.backref('systems'),
                                 secondary='origin_point_system_config',
                                 lazy='select', passive_deletes=True)

    def to_json(self, full: bool = True) -> Dict:
        """修改！！将SystemConfig对象转化成json格式的数据
        Args:
            full: True只会加上origin point desc（origin point 关联的point desc不会返回），False无point desc信息
        Returns:
            dict: SystemConfig对象序列化信息
        """
        json_str = {
            "cid": self.cid,
            "name": self.name,
            "parent": self.parent,
            "alias": self.alias,
            "children": self.children,
        }

        if full:
            origin_points = []
            for p in self.origin_points:
                origin_points.append(p.to_json(full=False))
            json_str['origin_points'] = origin_points
            json_str['points'] = origin_points
        if self.unit:
            json_str['unit'] = UnitSystem.get_by_id(self.unit).to_json()

        return json_str

    def __repr__(self):
        return '<System-{} {}>'.format(self.cid, self.name)

    def __eq__(self, __o: object) -> bool:
        return self.cid == __o.cid

    @classmethod
    def create_system_config(cls, name: str, parent: int, alias: str, unit: int, children: str = None):
        """ 使用前确保parent对应的System Config存在
        """
        with session_maker() as db_session:
            if parent:
                parent_sys = db_session.query(cls).filter(cls.cid == parent, cls.DELETED.is_(False)).first()
                origin_children = parent_sys.children
                if not origin_children:
                    new_children = name
                else:
                    new_children = '{},{}'.format(origin_children, name)
                parent_sys.children = new_children

            sys_config = SystemConfig(name=name, parent=parent, alias=alias, children=children, unit=unit, DELETED=False)
            db_session.add(sys_config)
            db_session.commit()
            db_session.refresh(sys_config)
            db_session.expunge(sys_config)
            return sys_config

    # @classmethod
    # def delete_system_configs(cls, cids):
    #     with session_maker() as db_session:
    #         for cid in cids:
    #             db_session.query(cls).filter(cls.cid == cid).update({'DELETED': True})

    @classmethod
    def update_system_config(cls, cid, data):
        with session_maker() as db_session:
            if 'parent' in data:
                new_parent = db_session.query(cls).filter(cls.cid == data['parent'], cls.DELETED.is_(False)).first()
                if not new_parent:
                    return False, '找不到指定上级系统-{}'.format(data['parent'])

                target_sys = db_session.query(cls).filter(cls.cid == cid, cls.DELETED.is_(False)).first()

                # 在新的父系统的children字段中加入当前系统
                new_name = data.get('name', target_sys.name)
                print(new_name)
                new_parent.children = '{},{}'.format(new_parent.children, new_name) if new_parent.children else new_name

                # 在旧的父系统的children字段中去掉当前系统
                origin_parent = db_session.query(cls).filter(cls.cid == target_sys.parent).first()
                new_children = origin_parent.children.split(',')
                try:
                    new_children.remove(target_sys.name)
                    origin_parent.children = ','.join(new_children)
                except:
                    pass
                target_sys.parent=data['parent']
            elif "name" in data:
                # 只对系统更改名称则将父系统中的children也进行更改
                target_sys = db_session.query(cls).filter(cls.cid == cid, cls.DELETED.is_(False)).first()
                parent_sys = db_session.query(cls).filter(cls.cid == target_sys.parent).first()
                new_name = data['name']
                children = parent_sys.children.split(',')
                try:
                    children.remove(target_sys.name)
                    children.append(new_name)
                    parent_sys.children = ",".join(children)
                except:
                    pass

            db_session.query(cls).filter(cls.cid == cid).update(data)
            return True, '修改成功'

    @classmethod
    def set_system_config_alias(cls, alias, cid=None, name=None):
        with session_maker() as db_session:
            if cid:
                db_session.query(cls).filter(cls.cid == cid).update(dict(alias=alias))
            elif name:
                db_session.query(cls).filter(cls.name == name).update(dict(alias=alias))
            elif not (cid and name):
                return False, "cid 和 name都为空"
            return True, "设置别名成功"

    @classmethod
    def delete_system_config(cls, cid) -> None:
        """修改！！ 删除时会同时去除多对多的联系
        Args:
            cid: str or int
        Returns:
            None
        """
        with session_maker() as db_session:
            target_sys = db_session.query(cls).get(cid)
            if target_sys.parent:
                parent_sys = db_session.query(cls).get(target_sys.parent)
                if parent_sys:
                    new_children = parent_sys.children.split(',')
                    # Exception . target_sys name not in new_children
                    new_children.remove(target_sys.name)
                    parent_sys.children = ','.join(new_children)
            target_sys.DELETED = True
            target_sys.origin_points.clear()

    @classmethod
    def get_all_in_unit(cls, unit, page=None, size=None):
        if page and size:
            with session_maker() as db_session:
                sys_configs = db_session.query(cls).filter(cls.DELETED.is_(False), cls.unit == unit).paginate(page=page, per_page=size, error_out=False)
                for sys in sys_configs.items:
                    db_session.expunge(sys)
                systems = sys_configs.items
                total = sys_configs.total
        else:
            with session_maker() as db_session:
                systems: List[SystemConfig] = db_session.query(cls).filter(cls.DELETED.is_(False), cls.unit == unit).all()
                total = 0
                for sys in systems:
                    for p in sys.origin_points:
                        db_session.expunge(p)
                    db_session.expunge(sys)
                    total += 1
        return systems, total

    @classmethod
    def get_all_id_and_names_in_unit(cls, unit):
        with session_maker() as db_session:
            systems = db_session.query(cls.cid, cls.name, cls.alias, cls.parent, cls.children) \
                .filter(cls.DELETED.is_(False), cls.unit == unit).all()
            return systems

    @classmethod
    def get_by_id(cls, cid, unit):
        with session_maker() as db_session:
            sys_config = db_session.query(cls).filter(cls.cid == cid, cls.DELETED.is_(False), cls.unit == unit).first()
            if sys_config:
                if sys_config.origin_points:
                    for p in sys_config.origin_points:
                        db_session.expunge(p)
                # db_session.refresh(sys_config)
                db_session.expunge(sys_config)
            return sys_config

    @classmethod
    def get_by_name(cls, name, unit):
        with session_maker() as db_session:
            sys_config = db_session.query(cls).filter(cls.name == name, cls.DELETED.is_(False), cls.unit == unit).first()
            if sys_config:
                if sys_config.origin_points:
                    for p in sys_config.origin_points:
                        db_session.expunge(p)
                db_session.expunge(sys_config)
            return sys_config
    
    @classmethod
    def get_by_alias(cls, alias, unit):
        with session_maker() as db_session:
            sys_config = db_session.query(cls).filter(cls.alias == alias, cls.DELETED.is_(False), cls.unit == unit).first()
            if sys_config:
                if sys_config.origin_points:
                    for p in sys_config.origin_points:
                        db_session.expunge(p)
                db_session.expunge(sys_config)
            return sys_config

    @classmethod
    def get_by_page(cls, unit: int, page, size):
        selected_systems, total = cls.get_all_in_unit(unit, page, size)
        return selected_systems, total

    @classmethod
    def get_by_parent(cls, parent_id):
        with session_maker() as db_session:
            children = db_session.query(cls).filter(cls.parent == parent_id, cls.DELETED.is_(False)).all()
            for child in children:
                for p in child.origin_points:
                    db_session.expunge(p)
                db_session.expunge(child)
            return children

    @classmethod
    def search_all(cls, name, alias, unit, page=None, size=None):
        with session_maker() as db_session:
            sys = db_session.query(cls).filter((cls.name.like('%' + name + '%')),
                                               (cls.alias.like('%' + alias + '%')),
                                               (cls.DELETED.is_(False)),
                                               (cls.unit == unit)).paginate(page=page, per_page=size, error_out=False)

            for sy in sys.items:
                if sy.origin_points:
                    for p in sy.origin_points:
                        db_session.expunge(p)
                db_session.expunge(sy)
            return sys.items, sys.total

    @classmethod
    def get_all_guide_systems(cls, unit: int, page=None, size=None):
        '''
        获取所有操作指导系统(已被OperGuideSystem.get_all_guide_systems替代)
        ----------
        Returns:
            res: 分页后dict组成的list
            total: 所有满足条件的记录的数量
        '''
        with session_maker() as db_session:
            guide_sid = db_session.query(cls.cid).filter(cls.name == "GUIDE", cls.unit == unit).first()
            guide_systems = db_session.query(cls.cid, cls.name, cls.alias).filter(cls.parent == guide_sid[0],
                                                                                  cls.DELETED.is_(False),
                                                                                  cls.unit == unit).paginate(page=page, per_page=size, error_out=False)

            res = [{
                'cid': cid,
                'name': name,
                'alias': alias
            } for cid, name, alias in guide_systems.items]

            return res, guide_systems.total

    @classmethod
    def update_guide_system(cls, cid, unit, data) -> None:
        with session_maker() as db_session:
            guide_sid = db_session.query(cls.cid).filter(cls.name == "GUIDE", cls.unit == unit).first()[0]
            db_session.query(cls).filter(cls.cid == cid, cls.parent == guide_sid, cls.DELETED.is_(False),
                                         cls.unit == unit).update(data)

    @classmethod
    def add_origin_points_to_systems(cls, cid: str, tag_names: List[str], unit: Union[str, int]):
        with session_maker() as db_session:
            from flask_app.models.origin_point_dec import OriginPointDesc
            system = db_session.query(cls).get(cid)
            if system is None:
                return f"系统 id:{cid} 不存在"
            err_list = []
            for tag_name in tag_names:
                origin_point = db_session.query(OriginPointDesc).filter(OriginPointDesc.tag_name == tag_name).first()
                if origin_point is not None:
                    if origin_point in system.origin_points:
                        err_list.append(f"原始点 {tag_name} 已存在")
                    else:
                        system.origin_points.append(origin_point)
                else:
                    err_list.append(f"原始点 {tag_name} 找不到")
            if len(err_list) > 0:
                return '; '.join(err_list)
            else:
                return "成功"

    @classmethod
    def modify_origin_points_to_systems(cls, cid: str, tag_names: List[str], unit: Union[str, int]):
        with session_maker() as db_session:
            from flask_app.models.origin_point_dec import OriginPointDesc
            system = db_session.query(cls).get(cid)
            if system is None:
                return f"系统 id:{cid} 不存在"
            names = db_session.query(OriginPointDesc.tag_name).filter(OriginPointDesc.tag_name.in_(tag_names)).all()
            valid_names = [name[0] for name in names]
            err_list = list(set(tag_names) - set(valid_names))

            now_origin_points_names = dict([(op.tag_name, op) for op in system.origin_points])
            new_origin_points_names = list(set(valid_names) - set(now_origin_points_names.keys()))
            delete_origin_points_names = list(set(now_origin_points_names.keys()) - set(valid_names))

            modify_origin_points = db_session.query(OriginPointDesc.tag_name, OriginPointDesc) \
                .filter(OriginPointDesc.tag_name.in_(valid_names)).all()
            modify_origin_points = dict(modify_origin_points)
            for del_origin_point in delete_origin_points_names:
                system.origin_points.remove(now_origin_points_names[del_origin_point])
            db_session.commit()

            system.origin_points.extend([point for name, point in modify_origin_points.items() if name in new_origin_points_names])
            db_session.commit()
            if len(err_list) > 0:
                return "无效点:" + ', '.join(err_list)
            else:
                return "成功"

    @classmethod
    def clear_table(cls, unit):
        # 模型映射  返回字典
        db.reflect(app=flask_app)
        # for table_name in db.metadata.tables:
        # get_engine 获得连接引擎 执行mysql命令
        db.get_engine().execute("SET FOREIGN_KEY_CHECKS = 0")
        db.get_engine().execute(f"DELETE FROM {cls.__tablename__} WHERE unit={unit}")
        db.get_engine().execute("SET FOREIGN_KEY_CHECKS = 1")
        return 'ok'

    @classmethod
    def upsert(cls, systems: List, unit: int):
        with session_maker() as db_session:
            rows = db_session.query(cls.name, cls.cid).filter(cls.unit == unit).all()
            # 获取数据库中存在的系统
            # print(rows)
            name_cid_map = dict(rows)
            # print(name_cid_map)
            for system in systems:
                # 存在则更新，否则插入
                if system.name in name_cid_map:
                    if system.parent:
                        system.parent = name_cid_map[system.parent]
                    else:
                        system.parent = None
                    db_session.query(cls).filter(cls.name == system.name, cls.unit == unit).update({
                        cls.parent: system.parent,
                        cls.children: system.children,
                    })
                else:
                    if system.parent:
                        system.parent = name_cid_map[system.parent]
                    else:
                        system.parent = None
                    db_session.add(system)
            db_session.commit()

    @classmethod
    def batch_add_origin_points_to_systems_list(cls, map: Dict[str, List[str]], unit: Union[str, int]):
        with session_maker() as db_session:
            from flask_app.models.origin_point_dec import OriginPointDesc
            for name, tag_names in map.items():
                system = db_session.query(cls).filter(cls.name == name, cls.unit == unit).first()
                origin_points = db_session.query(OriginPointDesc).filter(OriginPointDesc.tag_name.in_(tag_names)).all()
                system.origin_points = origin_points
