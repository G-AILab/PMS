from multiprocessing import Manager
from concurrent.futures import ProcessPoolExecutor
import pymysql
from flask_app.util.db.redis_util.util import Redis
from flask_app.util.db.influxDB_util.util import InfluxDB
from flask_cors import CORS
from flask_apscheduler import APScheduler
from flask_sqlalchemy import SQLAlchemy
from contextlib import contextmanager
from threading import Lock
from flask_app.util import process_manager
from pebble import ProcessPool
import multiprocessing

from flask import Flask
from flask_socketio import SocketIO
from flask_app.config import get_config
from flask_app.util.json import PowermodelJSONizer
from flask_app.websocket.redis_pub_sub import RedisPub
_get_config = get_config()

thread = None
thread_lock = Lock()
db = SQLAlchemy()
flask_app = Flask("power_model_system")

redis = Redis(host=_get_config.REDIS_HOST, port=_get_config.REDIS_PORT, db=0)
result_redis = Redis(host=_get_config.REDIS_HOST, port=_get_config.REDIS_PORT, db=1)
websocket_pub = RedisPub(redis)


influx = InfluxDB(
    host=_get_config.INFLUX_HOST, port=_get_config.INFLUX_PORT,
    username=_get_config.INFLUX_USERNAME, password=_get_config.INFLUX_PASSWORD,
    db=_get_config.INFLUX_DB
)

def init_flask_worker():
    flask_app.app_context().push()
    
def new_model_training_pool():
    return ProcessPool(max_workers=1,initializer=init_flask_worker, max_tasks=1, context=multiprocessing.get_context('spawn'))

def init_process_manager():
    process_manager.manager = Manager()
    process_manager.add_dataset_processes = process_manager.manager.dict()
    process_manager.train_processes = process_manager.manager.dict()
    process_manager.training_processes = process_manager.manager.dict()
    process_manager.select_processes = process_manager.manager.dict()
    process_manager.select_wait_processes = process_manager.manager.dict()
    process_manager.select_queue = process_manager.manager.Queue()
    process_manager.optimize_processes = process_manager.manager.dict()
    process_manager.optimizing_processes = process_manager.manager.dict()
    process_manager.auto_run_processes = process_manager.manager.dict()
    process_manager.auto_waiting_processes = process_manager.manager.dict()
    process_manager.fill_interval_process = process_manager.manager.dict()
    process_manager.append_points_process = process_manager.manager.dict()
    process_manager.update_dataset_processes = process_manager.manager.dict()
    process_manager.task_proc_pool = ProcessPool(max_workers=_get_config.TASK_POOL_SIZE,initializer=init_flask_worker, max_tasks=0, context=multiprocessing.get_context('spawn')) # ProcessPoolExecutor(max_workers=_get_config.TASK_POOL_SIZE)
    process_manager.model_training_pool = ProcessPool(max_workers=1,initializer=init_flask_worker, max_tasks=1, context=multiprocessing.get_context('spawn')) # ProcessPoolExecutor(max_workers=_get_config.TASK_POOL_SIZE)
    # scheduler.init_app(app)
    # scheduler.start()


# App Initialization
def initialize():
    init_process_manager()

def create_app() -> Flask:
    flask_app.config.from_object(_get_config)
    flask_app.config.from_object('flask_app.config.secure')  # 加载安全配置
    
    # celery.conf.update(flask_app.config)
    ctx = flask_app.app_context()
    ctx.push()
    CORS(flask_app, resources={r"/*": {"origins": "*"}}, support_credentials=True)
    db.init_app(flask_app)
    # scheduler.init_app(flask_app)
    with flask_app.app_context():
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
        # db.create_all()

    from flask_app.util.GreenPrint import GreenPrint
    from flask_app.api.dataset import dataset_blueprint
    from flask_app.api.model_api import model_blueprint
    from flask_app.api.user import user_blueprint
    from flask_app.api.role import role_blueprint
    from flask_app.api.token import token_blueprint
    from flask_app.api.algorithm import algorithm_blueprint
    from flask_app.api.system import sys_blueprint
    from flask_app.api.sub_system import subsys_blueprint
    from flask_app.api.system_config import sysconfig_blueprint
    from flask_app.api.reminder import reminder_blueprint
    from flask_app.api.oper_guide import guide_blueprint
    from flask_app.api.unit_system import unit_system_blueprint
    from flask_app.api.svg_graph import sys_graph_blueprint
    from flask_app.api.origin_point_desc import origin_point_blueprint
    from flask_app.api.point_desc import point_desc_blueprint
    from flask_app.api.inter_variable import inter_variable_blueprint
    from flask_app.api.extern_api import extern_blueprint
    from flask_app.api.pageconf import pageconf_blueprint
    api = GreenPrint('api', __name__, url_prefix='/api')
    api.register_blueprint(dataset_blueprint)
    api.register_blueprint(model_blueprint)
    api.register_blueprint(user_blueprint)
    api.register_blueprint(role_blueprint)
    api.register_blueprint(token_blueprint)
    api.register_blueprint(algorithm_blueprint)
    api.register_blueprint(sys_blueprint)
    api.register_blueprint(subsys_blueprint)
    api.register_blueprint(sysconfig_blueprint)
    api.register_blueprint(reminder_blueprint)
    api.register_blueprint(guide_blueprint)
    api.register_blueprint(unit_system_blueprint)
    api.register_blueprint(sys_graph_blueprint)
    api.register_blueprint(origin_point_blueprint)
    api.register_blueprint(point_desc_blueprint)
    api.register_blueprint(inter_variable_blueprint)
    api.register_blueprint(extern_blueprint)
    api.register_blueprint(pageconf_blueprint)


    flask_app.json_encoder = PowermodelJSONizer

    flask_app.register_blueprint(api)
    return flask_app


@contextmanager
def session_maker(session=db.session, print_close=False):
    try:
        yield session
        session.commit()
    except Exception as e:
        print(e)
        session.rollback()
        raise
    finally:
        session.close()
        if print_close:
            print('session closed!')


def get_websocket_app(app):
    # message_queue 负责进程间websocket的信息同步， 保证在新开的进程中也可以正常发送信息
    # redis_url = 'redis://{}:{}/2'.format(_get_config.REDIS_HOST, _get_config.REDIS_PORT)
    # socket_io = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet', message_queue=redis_url)
    socket_io = SocketIO(app, cors_allowed_origins='*')
    return socket_io
