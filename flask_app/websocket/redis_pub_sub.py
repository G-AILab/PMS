import json
import time
from re import I
import flask_app.util.db.redis_util.util as util
from flask_app.config import get_config
from flask_app.util.db.redis_util.util import Redis

config = get_config()
host = config.REDIS_HOST
port = config.REDIS_PORT
redis_obj = Redis(host=host, port=port, db=0)

CHANNEL = {
    'realtime_channel': 'realtime',
    'predict_channel': 'predict',
    'warning_channel': 'warning',
    'selection_channel': 'selection',
    'optimize_channel': 'optimize',
    'train_channel': 'train',
    'autorun_channel': 'auto_run',
    'detection_channel': 'detection',
    'add_dataset_channel': 'add_dataset',
    'point_check_expect_channel': 'point_check_expect',
    'point_check_actual_channel': 'point_check_actual',
    'point_check_upper_channel': 'point_check_upper',
    'point_check_lower_channel': 'point_check_lower',
    'point_check_offset_channel': 'point_check_offset',
    'point_check_switch_channel': 'point_check_switch',
    'point_check_variance_channel': 'point_check_variance',
    'download_process_channel': 'download_process',
    'get_sid_channel': 'download_sid'
}

ROOMS = set({'1', '2', '3', '4'})


class RedisPub(object):
    def __init__(self, rs: util.Redis):
        self.rs = rs
        self.channels = CHANNEL

    def _supp_data(self, unit, data):
        self._check_data(data)

        data = {
            'unit': unit,
            'data': data
        }
        return json.dumps(data)

    def _check_data(self, data):
        # if not isinstance(data,dict):
        #     raise Exception("publish_x function data params type error,not a dict")
        try:
            json.dumps(data)
        except Exception as e:
            print("[ERROR] RedisPub _check_data function can't dumps data. ERROR is :", e)
            raise Exception("data is not a serializable object")

    def publish_realtime(self, unit, data):
        return self.publish_data(self.channels['realtime_channel'], unit, data)

    def publish_predict(self, unit, data):
        return self.publish_data(self.channels['predict_channel'], unit, data)

    def publish_warning(self, unit, data):
        return self.publish_data(self.channels['warning_channel'], unit, data)

    def publish_expect(self, unit, data):
        # 发送期望值数据
        return self.publish_data(self.channels['expect_channel'], unit, data)
    
    def publish_data(self, channel, unit, data):
        try:
            data = self._supp_data(unit, data)
            self.rs.publish(channel, data)
            return True, "publish success"
        except Exception as e:
            print(f"[{time.strftime('%F %T')} ERROR]")
            return False, f"publish error,{e}"


# 发布端
redis_pub = RedisPub(redis_obj)


def subscribe_redis(redis_db):
    channels = list(CHANNEL.values())
    pubsub = redis_db.subscribe(channels[0])
    for channel in channels:
        pubsub.subscribe(channel)
    return pubsub


# 订阅端
redis_sub = subscribe_redis(redis_obj)
