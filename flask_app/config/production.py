from flask_app.config.default import Config

class ProductionConfig(Config):
    REMOTE_SERVERS = [
        ('248', 'admin1', '172.17.86.16', 22),
        ('247', 'grid', '172.16.0.1', 22),
    ]

    DEBUG = True
    JOBS = [
        {
            'id': 'realtime_eval',
            'func': '__main__:realtime_eval_task',
            'args': (),
            'trigger': 'interval',
            'seconds': Config.REALTIME_EVAL_CYCLE,
            'max_instances': Config.APS_MAX_INSTANCE,
            'misfire_grace_time': 10,
            'coalesce': True
        },
        {
            'id': 'server_usage',
            'func': '__main__:get_remote_server_stats',
            'args': (),
            'trigger': 'interval',
            'seconds': 5,
            'max_instances': Config.APS_MAX_INSTANCE,
            'misfire_grace_time': 1,
            'coalesce': True
        },
        {
        'id': 'check_points',
        'func': '__main__:point_check_task',
        'args': (),
        'trigger': 'interval',
        'seconds': Config.POINT_CHECK_CYCLE,
        'misfire_grace_time': 10,
        'max_instances': Config.APS_MAX_INSTANCE,
        'coalesce': True
        },
        {
            'id': 'check_model_processes',
            'func': '__main__:check_processes_task',
            'args':(),
            'trigger': 'interval',
            'seconds': Config.MODEL_TASK_CHECK_INTERVAL,
            'max_instances': Config.APS_MAX_INSTANCE,
            'coalesce': True
        }
    ]

    SQLALCHEMY_DATABASE_URI = 'mysql://root:root@mysql:3306/power_model'

    REDIS_HOST = "redis"
    REDIS_PORT = 6379

    INFLUX_HOST = "influxdb"
    INFLUX_PORT = 8086


    REMOTE_HOST = "172.17.86.16"
    REMOTE_PORT = 28888



class ChenZhu247Config(Config):
    REMOTE_SERVERS = [
        ('248', 'admin1', '172.17.86.16', 22),
        ('247', 'grid', '172.17.86.17', 22),
    ]

    DEBUG = True
    JOBS = [
    {
        'id': 'realtime_eval',
        'func': '__main__:realtime_eval_task',
        'args': (),
        'trigger': 'interval',
        'seconds': Config.REALTIME_EVAL_CYCLE,
        'max_instances': Config.APS_MAX_INSTANCE,
        'misfire_grace_time': 10,
        'coalesce': True
    },
    {
        'id': 'server_usage',
        'func': '__main__:get_remote_server_stats',
        'args': (),
        'trigger': 'interval',
        'seconds': 5,
        'max_instances': Config.APS_MAX_INSTANCE,
        'misfire_grace_time': 1,
        'coalesce': True
    },
    {
       'id': 'check_points',
       'func': '__main__:point_check_task',
       'args': (),
       'trigger': 'interval',
       'seconds': Config.POINT_CHECK_CYCLE,
       'misfire_grace_time': 10,
       'max_instances': Config.APS_MAX_INSTANCE,
       'coalesce': True
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
    ]

    SQLALCHEMY_DATABASE_URI = 'mysql://root:root@mysql:3306/power_model'

    REDIS_HOST = "redis"
    REDIS_PORT = 6379

    INFLUX_HOST = "influxdb"
    INFLUX_PORT = 8086

    REMOTE_HOST = "172.17.86.16"
    REMOTE_PORT = 28888


class ChenZhu248Config(Config):
    DEBUG = False
    # 试图获取资源利用率的服务器列表 (名称, username, host, port)
    POINT_CHECK_CYCLE = 3
    CELERYD_CONCURRENCY = 1500
    REMOTE_SERVERS = [
        ('248', 'admin1', '172.17.86.16', 22),
        ('247', 'grid', '172.17.86.17', 22),
    ]
    JOBS = [
    {
        'id': 'realtime_eval',
        'func': '__main__:realtime_eval_task',
        'args': (),
        'trigger': 'interval',
        'seconds': Config.REALTIME_EVAL_CYCLE,
        'max_instances': Config.APS_MAX_INSTANCE,
        'misfire_grace_time': 10,
        'coalesce': True
    },
    {
        'id': 'server_usage',
        'func': '__main__:get_remote_server_stats',
        'args': (),
        'trigger': 'interval',
        'seconds': 5,
        'max_instances': Config.APS_MAX_INSTANCE,
        'misfire_grace_time': 1,
        'coalesce': True
    },
    {
       'id': 'check_points',
       'func': '__main__:point_check_task',
       'args': (),
       'trigger': 'interval',
       'seconds': 2,
       'misfire_grace_time': 1,
       'max_instances': 1,
       'coalesce': True
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
    ]

    SQLALCHEMY_DATABASE_URI = 'mysql://root:root@mysql:3306/power_model'

    REDIS_HOST = "redis"
    REDIS_PORT = 6379

    INFLUX_HOST = "influxdb"
    INFLUX_PORT = 8086

    REMOTE_HOST = "172.17.86.16"
    REMOTE_PORT = 28888



class CeleryNode247(Config):
    DEBUG = False
    # 试图获取资源利用率的服务器列表 (名称, username, host, port)
    POINT_CHECK_CYCLE = 3
    CELERYD_CONCURRENCY = 100
    REMOTE_SERVERS = [
        # ('248', 'admin1', '172.17.86.16', 22),
        # ('247', 'grid', '172.17.86.17', 22),
    ]
    JOBS = [
    {
        'id': 'realtime_eval',
        'func': '__main__:realtime_eval_task',
        'args': (),
        'trigger': 'interval',
        'seconds': Config.REALTIME_EVAL_CYCLE,
        'max_instances': Config.APS_MAX_INSTANCE,
        'misfire_grace_time': 10,
        'coalesce': True
    },
    {
        'id': 'server_usage',
        'func': '__main__:get_remote_server_stats',
        'args': (),
        'trigger': 'interval',
        'seconds': 5,
        'max_instances': Config.APS_MAX_INSTANCE,
        'misfire_grace_time': 1,
        'coalesce': True
    },
    {
       'id': 'check_points',
       'func': '__main__:point_check_task',
       'args': (),
       'trigger': 'interval',
       'seconds': 2,
       'misfire_grace_time': 1,
       'max_instances': 1,
       'coalesce': True
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
    ]

    SQLALCHEMY_DATABASE_URI = 'mysql://root:root@172.17.86.16:3306/power_model'

    REDIS_HOST = "172.17.86.16"
    REDIS_PORT = 6379

    INFLUX_HOST = "172.17.86.16"
    INFLUX_PORT = 8086

    REMOTE_HOST = "172.17.86.16"
    REMOTE_PORT = 28888