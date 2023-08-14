class DevConfig:
    DEBUG = True
    SQL_PORT = 3306
    SQLALCHEMY_DATABASE_URI = f'mysql://root:root@mysql:{SQL_PORT}/power_model'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    REDIS_HOST = "redis"
    REDIS_PORT = 6379
    REDIS_DB = 0
    REDIS_EXPIRE = 14400
    INFLUX_HOST = "influxdb"
    INFLUX_PORT = 8086
    INFLUX_USERNAME = 'root'
    INFLUX_PASSWORD = 'root'
    INFLUX_DB = 'test'
    ALLOWED_EXTENSIONS = ['py', 'txt']
    UPLOAD_FOLDER = 'flask_app/uploads'
    FLASK_URL = 'http://hd.miaoguoge.xyz:22222'
    REMOTE_HOST = "172.17.86.16"
    REMOTE_PORT = 28888

    # 首页默认的四个实时预测字段
    PREDICTION = ['N3DCS.3TEMS106AI', 'N3TB.N3BC_T_AHGasOut', 'N3TB.N3TC_R_WaterRep', 'N3TB.N3BC_RateW_MillC']
    # 首页默认的四个异常检测字段
    DETECTION = ['N3DCS.3TEMS106AI', 'N3TB.N3BC_T_AHGasOut', 'N3TB.N3TC_R_WaterRep', 'N3TB.N3BC_RateW_MillC']

    # 实时数据传输间隔（秒）
    REALTIME_DATA_STEP = 3
    # 最多同时训练的模型数
    MAX_TRANING_MODELS = 1
    # redis中预测结果过期时间（秒）
    MODEL_RES_EXPIRE_TIME = 14400
    
    # 实时评估间隔时间（秒）
    REALTIME_EVAL_CYCLE = 600
    # 实时评估结果过期时间（秒）
    REALTIME_EVAL_EXTIME = 86400
    # 实时评估任务开始报警判断的最小评估结果个数
    MIN_EVAL_RESULTS = 12

    # 试图获取资源利用率的服务器列表 (名称, username, host, port)
    REMOTE_SERVERS = [
        # ('248', 'admin1', '', 22),
        ('247', 'grid', '172.17.0.1', 22),
    ]
    # 服务器资源使用情况结果文件保存位置
    SERVER_STAT_RES_DIR = '/workspace/tmp/server_usages'
    # ssh密钥保存位置
    PRIVATE_KEY_PATH = '/root/.ssh/id_rsa'

    # point_check任务周期（秒）
    POINT_CHECK_CYCLE = 3

    # apschedule任务最大并发数
    APS_MAX_INSTANCE = 20
    # apschedule任务列表
    JOBS = [
        # {
        #     'id': 'realtime_eval',
        #     'func': '__main__:realtime_eval_task',
        #     'args': (),
        #     'trigger': 'interval',
        #     'seconds': REALTIME_EVAL_CYCLE,
        #     'max_instances': APS_MAX_INSTANCE,
        #     'misfire_grace_time': 10,
        #     'coalesce': True
        # },
        # {
        #     'id': 'server_usage',
        #     'func': '__main__:get_remote_server_stats',
        #     'args': (),
        #     'trigger': 'interval',
        #     'seconds': 5,
        #     'max_instances': APS_MAX_INSTANCE,
        #     'misfire_grace_time': 10,
        #     'coalesce': True
        # },
        # {
        #     'id': 'check_points',
        #     'func': '__main__:point_check_task',
        #     'args': (),
        #     'trigger': 'interval',
        #     'seconds': POINT_CHECK_CYCLE,
        #     'misfire_grace_time': 10,
        #     'max_instances': APS_MAX_INSTANCE,
        #     'coalesce': True
        # }
    ]

    # accept_content = ['application/x-python-serialize']
