from flask_app import db
from flask_app import session_maker
from flask_app import flask_app
from sqlalchemy import Table, inspect
from sqlalchemy.dialects.mysql import insert

origin_point_system_config = Table(
    'origin_point_system_config',
    db.Model.metadata,
    db.Column('origin_point', db.String(30), db.ForeignKey('origin_point_desc.tag_name', ondelete='CASCADE'), primary_key=True),
    db.Column('system_config', db.Integer, db.ForeignKey('system_config.cid', ondelete='CASCADE'), primary_key=True)
)


def clear_origin_point_system_table(unit):
    db.reflect(app=flask_app)
    db.get_engine().execute("SET foreign_key_checks = 0")
    db.get_engine().execute(f"DELETE FROM {'origin_point_system_config'} WHERE origin_point in (select tag_name FROM origin_point_desc WHERE unit={unit});")
    db.get_engine().execute("SET foreign_key_checks = 1")
    return 'ok'


#  通过业务逻辑来限制origin point desc和point desc的联系，SQL上不做限制！！

def add_all(map_list):
    with session_maker() as db_session:
        db_session.add_all(map_list)
        db_session.commit()
        return "ok"


def add(relation_map):
    with session_maker() as db_session:
        db_session.add(relation_map)
        db_session.commit()
        return "ok"


def upsert_all(entity: type, records: list):
    """
    一次性将对应实体entity的多组数据进行upsert操作

    Args:
        entity (type): 表对应的实体类名
        records (list): 需要upsert的数据组成的列表

    Returns:
        bool: 返回是否upsert成功
    """
    # 获取所有主键属性名称列表
    primary_keys = [col.name for col in inspect(entity).primary_key]
    # 获取全部字段名称列表
    total_fields = inspect(entity).c.keys()
    # 需要更新的字段名称列表
    update_keys = [key for key in total_fields if key not in primary_keys]
    
    insert_stmt = insert(entity).values(records)
    
    # 主键已存在时需要更新的列，其实就是除主键以外的全部列
    update_columns = {x.name: x for x in insert_stmt.inserted if x.name in update_keys}
    # 当遇上关系表这样的多对多并且全部字段组成复合主键时，不存在则插入，存在则更新全部字段
    if not len(update_columns):
        update_columns = {x.name: x for x in insert_stmt.inserted if x.name in total_fields}
    
    upsert_stmt = insert_stmt.on_duplicate_key_update(**update_columns)
    
    db.session.execute(upsert_stmt)
    db.session.commit()
