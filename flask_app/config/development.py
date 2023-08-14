from flask_app.config.default import Config


class DevelopmentConfig(Config):
    DEBUG = True

    # 试图获取资源利用率的服务器列表 (名称, username, host, port)
    REMOTE_SERVERS = [
        # ('248', 'admin1', '172.17.86.16', 22),
        # ('247', 'grid', '172.16.0.1', 22),
    ]

    # apschedule任务最大并发数
    APS_MAX_INSTANCE = 10
    # apschedule任务列表
    JOBS = [
        {
            'id': 'realtime_eval',
            'func': '__main__:realtime_eval_task',
            'args': (),
            'trigger': 'interval',
            'seconds': Config.REALTIME_EVAL_CYCLE,
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
            'seconds': Config.POINT_CHECK_CYCLE,
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
            'seconds': Config.MODEL_TASK_CHECK_INTERVAL,
            'max_instances': APS_MAX_INSTANCE,
            'coalesce': False
        }
    ]



class TestingConfig(Config):
    DEBUG = True

    SQLALCHEMY_DATABASE_URI = 'mysql://root:root@192.168.0.102:13306/power_model'

    REDIS_HOST = "192.168.0.102"
    REDIS_PORT = 3377
    REDIS_DB = 0
    REDIS_EXPIRE = 60

    INFLUX_HOST = "192.168.0.102"
    INFLUX_PORT = 8085

    CELERY_BROKER_URL = 'redis://192.168.0.102:3377/5'
    CELERY_RESULT_BACKEND = 'redis://192.168.0.102:3377/3'


class LocalConfig(Config):
    DEBUG = True
    JOBS = []

    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:root@192.168.100.251:3311/power_model'

    REDIS_HOST = '192.168.100.251'
    REDIS_PORT = 6385
    INFLUX_HOST = '192.168.100.251'
    INFLUX_PORT = 8091

    CELERY_BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/5'
    CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/3'

    REMOTE_HOST = "172.17.86.16"
    REMOTE_PORT = 28888

