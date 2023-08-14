# from gevent import monkey
# monkey.patch_all(thread=False, socket=False)
import multiprocessing

#debug = True
loglevel = 'debug'
bind = '0.0.0.0:8888' #绑定与Nginx通信的端口
pidfile = '/var/log/gunicorn/gunicorn.pid'
accesslog = '/var/log/gunicorn/access.log'
errorlog = '/var/log/gunicorn/debug.log'
daemon = False
workers = 10
worker_class = 'gthread' #默认为阻塞模式，最好选择gevent模式 eventlet,  gevent, sync , tornado 
threads = 10