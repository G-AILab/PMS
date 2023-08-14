import pymysql

from flask_apscheduler import APScheduler
from flask_app import db as aps_db
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from flask_app.config import get_config
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from flask_app.util.db.redis_util.util import Redis


_get_config = get_config()

# aps_db = SQLAlchemy()

scheduler = BackgroundScheduler()
flask_aps = APScheduler(scheduler)

redis = Redis(host=_get_config.REDIS_HOST, port=_get_config.REDIS_PORT, db=0)
result_redis = Redis(host=_get_config.REDIS_HOST, port=_get_config.REDIS_PORT, db=1)


def create_aps_app() -> Flask:
    # app = create_aps_app()
    app = Flask("power_model_system_apscheduler")
    app.config.from_object(_get_config)

    ctx = app.app_context()
    ctx.push()

    aps_db.init_app(app)
    with app.app_context():
        pymysql.install_as_MySQLdb()
        from flask_app.models.sub_system import SubSystem
        from flask_app.models.model import Model
        from flask_app.models.model_timer import Model_timer
        from flask_app.models.user import User
        from flask_app.models.dataset import Dataset
        from flask_app.models.algorithm import Algorithm
        from flask_app.models.system_config import SystemConfig
        from flask_app.models.point_desc import PointDesc
        from flask_app.models.reminder import Reminder
        from flask_app.models.inter_variable import InterVariable
        from flask_app.models.oper_guide_system import OperGuideSystem
        from flask_app.models.oper_guide_step import OperGuideStep
        from flask_app.models.unit_system import UnitSystem
        from flask_app.models.system_graph import SystemGraph
        from flask_app.models.system_graph_point import SystemGraphPoint
        from flask_app.models.origin_point_dec import OriginPointDesc
        from flask_app.models.relation_map import origin_point_system_config
    
    return app


# 因为 sqlachemy 多线程会出问题，我们需要每个线程一个 app，多个线程共享一个app init 的 db 会有线程安全问题
app = create_aps_app()
guide_app = create_aps_app()
t_app = create_aps_app()
