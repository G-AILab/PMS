from flask_app.config import get_config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from redis import Redis
from flask_app.models.origin_point_dec import OriginPointDesc, PointType
from flask_app.models.inter_variable import InterVariable
import pymysql
import json


def init_origin_point_names():
    pymysql.install_as_MySQLdb()

    tablename = OriginPointDesc.__tablename__
    inter_tablename = InterVariable.__tablename__
    _get_config = get_config()
    engine = create_engine(_get_config.SQLALCHEMY_DATABASE_URI)
    redis = Redis(host=_get_config.REDIS_HOST, port=_get_config.REDIS_PORT, db=0)

    with engine.connect() as conn:
        result = conn.execute(text(f"select {tablename}.tag_name,{tablename}.point_type from {tablename} "))
        result = result.all()
        origin_points = [item[0] for item in result if item[1] == PointType.ORIGINPOINTDESC.value]
        inter_variables_result = conn.execute(text(f"select {inter_tablename}.var_name,{inter_tablename}.var_value from {inter_tablename} "))
        inter_variables = dict(inter_variables_result.all())

        origin_point_names = "origin_point_names"
        inter_variables_names = "inter_variable_names"
        auto = "all_points"
        origin_point_flag = "origin_point_flag"
        inter_variable_flag = "inter_variable_flag"

        redis.set(origin_point_names, ",".join(origin_points), ex=None)
        redis.set(inter_variables_names, json.dumps(inter_variables), ex=None)
        redis.set(auto, ",".join([*origin_points, *(list(inter_variables.keys()))]), ex=None)
        redis.set(origin_point_flag, "True", ex=None)
        redis.set(inter_variable_flag, "True", ex=None)
        redis.persist(origin_point_names)
        redis.persist(inter_variables_names)
        redis.persist(auto)
        redis.persist(origin_point_flag)
        redis.persist(inter_variable_flag)
