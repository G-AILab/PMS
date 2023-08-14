# from gevent import monkey
# monkey.patch_all(thread=False, socket=False)
# monkey.patch_all()
import multiprocessing

#debug = True
loglevel = 'debug'
bind = '0.0.0.0:8010' #绑定与Nginx通信的端口
pidfile = '/var/log/gunicorn/sio_gunicorn.pid'
accesslog = '/var/log/gunicorn/sio_access.log'
errorlog = '/var/log/gunicorn/sio_debug.log'
daemon = False
workers = 1 # multiprocessing.cpu_count() * 2 + 1
worker_class = 'eventlet' #默认为阻塞模式，最好选择gevent模式 eventlet,  gevent, sync , tornado,threading

