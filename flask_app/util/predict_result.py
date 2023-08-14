import time
from flask_socketio import emit
from numpy import broadcast
from flask_app import result_redis
import json
from flask_app import flask_app


def send_realtime_predict_results(ts):
    if ts is None:
      ts = time.time()
    ts = int(ts)
    ts = str(ts)
    with flask_app.app_context():
        result = result_redis.scan_keys(ts)
        data = [json.loads(item) for item in result]
        res = {'data': data}
        emit('predict', res, broadcast=True, namespace='/websocket')
    return 


