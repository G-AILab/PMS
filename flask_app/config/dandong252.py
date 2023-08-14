from flask_app.config.default import Config


class DanDong252(Config):
    DEBUG = True

    # 试图获取资源利用率的服务器列表 (名称, username, host, port)
    REMOTE_SERVERS = [
        ('252','grid', '172.17.51.169', 22),
        # ('248', 'admin1', '172.17.86.16', 22),
        # ('247', 'grid', '172.16.0.1', 22),
    ]

    # apschedule任务最大并发数
    APS_MAX_INSTANCE = 20
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
            'coalesce': True
        },
        {
            'id': 'server_usage',
            'func': '__main__:get_remote_server_stats',
            'args': (),
            'trigger': 'interval',
            'seconds': 5,
            'max_instances': APS_MAX_INSTANCE,
            # 'misfire_grace_time': 10,
            'coalesce': True
        },
        {
            'id': 'check_points',
            'func': '__main__:point_check_task',
            'args': (),
            'trigger': 'interval',
            'seconds': Config.POINT_CHECK_CYCLE,
            # 'misfire_grace_time': 10,
            'max_instances': APS_MAX_INSTANCE,
            'coalesce': True
        }
    ]

