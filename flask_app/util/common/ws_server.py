import eventlet
import socketio
import redis
import time
from threading import Lock
import random

from flask_app import get_config

_get_config = get_config()

r = redis.Redis(host=_get_config.REDIS_HOST, port=_get_config.REDIS_HOST, db=0, decode_responses=True)
r2 = redis.Redis(host=_get_config.REDIS_HOST, port=_get_config.REDIS_HOST, db=1, decode_responses=True)

sio = socketio.Server(cors_allowed_origins='*')
thread = None
thread_lock = Lock()

def create_serve():
    app = socketio.WSGIApp(sio, static_files={
        '/': {'content_type': 'text/html', 'filename': 'index.html'}
    })
    @sio.event
    def connect(sid, environ):
        print('connect ', sid)
        global thread
        with thread_lock:
            if thread is None:
                thread = sio.start_background_task(target=background_thread)

    # @sio.on('client')
    # def on_message(sid, data):
    #     print('serve received a message!111', data)
    @sio.on('client')
    def another_event(sid, data):
        print('serve received a message!', data)
    @sio.event
    def my_event(sid, data):
        print('message ', data)
        sio.emit('test', {'response': 'connert success'})
    @sio.event
    def disconnect(sid):
        print('disconnect ', sid)
    
    def background_thread():
        keys_list = ['N3DCS.3LTCD315S', 'N3DCS.3CCSHPBYPTMP', 'N3DCS.80HTK52CT012', 'N3DCS.3FTFW107AI', 'CN3TB.N3TS_W_CGB', 'CN3TB.N3TS_P_8LHS']
        while True:
            sio.sleep(1)
            ts = str(int(time.time()))
            for k in keys_list:
                key = k + '-' + ts
                value = r2.get(key)
                sio.emit('serve', {'data': value})

        
    
    if __name__ == '__main__':
        eventlet.wsgi.server(eventlet.listen(('', 8889)), app)

create_serve()

