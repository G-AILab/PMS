class Config:
    DEBUG = False
    SQL_PORT = 3306
    #mysql+mysqldb://scott:tiger@localhost/foo
    SQLALCHEMY_DATABASE_URI = f'mysql+mysqldb://root:root@mysql:{SQL_PORT}/power_model'
    # SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_TRACK_MODIFICATIONS = True

    CELERYD_MAX_TASKS_PER_CHILD = 1
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 30,  # 数据库连接刷新时间
        'pool_timeout': 10,  # 数据库连接超时时间
        'pool_size': 50,  # 数据库连接池大小
    }
    # 最多运行的模型个数
    CELERYD_CONCURRENCY = 200
    JSONIFY_PRETTYPRINT_REGULAR = False
    JSON_SORT_KEYS = False
    REDIS_HOST = "redis"
    REDIS_PORT = 6379
    REDIS_DB = 0
    REDIS_EXPIRE = 60
    INFLUX_HOST = "influxdb"
    INFLUX_PORT = 8086
    INFLUX_USERNAME = 'root'
    INFLUX_PASSWORD = 'root'
    INFLUX_DB = 'test'
    ALLOWED_EXTENSIONS = ['py', 'txt']
    UPLOAD_FOLDER = 'flask_app/uploads'
    FLASK_URL = 'http://hd.miaoguoge.xyz:22222'
    SECRET_KEY = 'asdfsdafsdaf134561sdaf'

    # 首页默认的四个实时预测字段
    PREDICTION = ['N3DCS.3TEMS106AI', 'N3TB.N3BC_T_AHGasOut', 'N3TB.N3TC_R_WaterRep', 'N3TB.N3BC_RateW_MillC']
    # 首页默认的四个异常检测字段
    DETECTION = ['N3DCS.3TEMS106AI', 'N3TB.N3BC_T_AHGasOut', 'N3TB.N3TC_R_WaterRep', 'N3TB.N3BC_RateW_MillC']

    # 实时数据传输间隔（秒）
    REALTIME_DATA_STEP = 1
    # redis中预测结果过期时间（秒）
    MODEL_RES_EXPIRE_TIME = 14400
    MODEL_RUNNNING_TIME = 2
    
    # 模型任务进程池大小
    TASK_POOL_SIZE = 48
    
    # 最多同时训练的模型数
    MAX_TRANING_MODELS = 1
    # 最多同时特征选择的模型数
    MAX_SELECTING_MODELS = 2
    
    # 实时评估间隔时间（秒）
    REALTIME_EVAL_CYCLE = 600
    # 实时评估结果过期时间（秒）
    REALTIME_EVAL_EXTIME = 86400
    # 实时评估任务开始报警判断的最小评估结果个数
    MIN_EVAL_RESULTS = 12

    # 试图获取资源利用率的服务器列表 (名称, username, host, port)
    REMOTE_SERVERS = [
        ('248', 'admin1', '172.17.86.16', 22),
        ('247', 'grid', '172.16.0.1', 22),
    ]
    # 服务器资源使用情况结果文件保存位置
    SERVER_STAT_RES_DIR = '/workspace/tmp/server_usages'
    # ssh密钥保存位置
    PRIVATE_KEY_PATH = '/root/.ssh/id_rsa'

    # point_check任务周期（秒）
    POINT_CHECK_CYCLE = 3
    # point_check任务新增预警记录的间隔（秒）
    REMINDER_INSERT_INTERVAL = 30 * 60
    # point_check任务刷新预警规则的间隔（秒）
    REMINDER_RULES_UPDATE_INTERVAL = 10 * 60

    # 模型任务进程失活检查间隔（秒）
    MODEL_TASK_CHECK_INTERVAL = 1 * 60

    # apschedule任务最大并发数
    APS_MAX_INSTANCE = 20
    # apschedule任务列表
    JOBS = [
        {
            'id': 'realtime_eval',
            'func': '__main__:realtime_eval_task',
            'args': (),
            'trigger': 'interval',
            'seconds': REALTIME_EVAL_CYCLE,
            'max_instances': APS_MAX_INSTANCE,
            # 'misfire_grace_time': 10,
            'coalesce': False
        },
        {
            'id': 'server_usage',
            'func': '__main__:get_remote_server_stats',
            'args': (),
            'trigger': 'interval',
            'seconds': 5,
            'max_instances': APS_MAX_INSTANCE,
            # 'misfire_grace_time': 10,
            'coalesce': False
        },
        {
            'id': 'check_points',
            'func': '__main__:point_check_task',
            'args': (),
            'trigger': 'interval',
            'seconds': POINT_CHECK_CYCLE,
            # 'misfire_grace_time': 10,
            'max_instances': 1,
            'coalesce': False
        },
        {
            'id': 'oper_guide_check',
            'func': '__main__:oper_guide_task',
            'args': (),
            'trigger': 'interval',
            'seconds': 3,
            'max_instances': 1,
            'coalesce': True
        },
        {
            'id': 'check_model_processes',
            'func': '__main__:check_processes_task',
            'args':(),
            'trigger': 'interval',
            'seconds': MODEL_TASK_CHECK_INTERVAL,
            'max_instances': APS_MAX_INSTANCE,
            'coalesce': False
        }
    ]
    # apschedule executors
    SCHEDULER_EXECUTORS = {
        'default': {
            'type': 'threadpool',
            'max_workers': 100
        },
        # 'processpool': {
        #     'type': 'processpool',
        #     'max_workers': 10
        # }
    }

    # accept_content = ['application/x-python-serialize']
    REMOTE_HOST = "172.17.86.16"
    REMOTE_PORT = 28888

    # 对外接口所用点的定义excel所在文件夹
    EXTERN_EXCEL_DIR = '/workspace/power_model_system/extern_files'

    #RPC 先这是默认在一台服务器上
    RPC_IP = "127.0.0.1"
    RPC_PORT = 28557
