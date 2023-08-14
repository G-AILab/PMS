from flask_app.config.default import Config


class New(Config):
    DEBUG = True

    # 试图获取资源利用率的服务器列表 (名称, username, host, port)
    REMOTE_SERVERS = [
        ('252','grid', '172.17.51.169', 22),
        # ('248', 'admin1', '172.17.86.16', 22),
        # ('247', 'grid', '172.16.0.1', 22),
    ]
