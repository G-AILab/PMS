import redis
import time
import collections
import pickle
import os
import random

# from flask_app import get_config
import json

ip = 'redis'
port = 6379
REDIS_EXPIRE_TIME = 14400  # 插入的数据的过期时间

r = redis.Redis(host=ip, port=port, db=0, decode_responses=True)
# r2 = redis.Redis(host=ip, port=3377, db=1, decode_responses=True)
dq = collections.deque()


with open('/workspace/data/test_2_day_2_1648208681.pickle','rb') as f:
    df = pickle.load(f)

for i in range(0, df.shape[0]):
     dq.append(df.iloc[i])


def timer(keys):
    '''
    定时写入redis（每秒）
    ----------
    ----------
    '''
    current_time = int(time.time())
    previous_time = current_time
    while True:
        previous_time = current_time
        current_time = int(time.time())
        if current_time - previous_time >= 1:
            series = dq[0]
            # print(series[0])
            key_values = [('{}@{}'.format(current_time, keys[i]), series[i]) for i in range(len(keys))]

            with r.pipeline(transaction=False) as p:
                for key, value in key_values:
                    p.setex(key, REDIS_EXPIRE_TIME, value)
                p.set('latest', current_time)
                p.execute()
            r.set('latest', str(current_time))
            print(current_time)

            # for i in range(len(keys)):
            #     if (i == 0):
            #         opc_dict[keys[0]] = current_time
            #         print(current_time)
            #     else:
            #         opc_dict[keys[i]] = series[i-1]
            dq.popleft()
            dq.append(series)
            # key = str(current_time)
            # keys_list = ['N3DCS.3LTCD315S', 'N3DCS.3CCSHPBYPTMP', 'N3DCS.80HTK52CT012', 'N3DCS.3FTFW107AI', 'CN3TB.N3TS_W_CGB', 'CN3TB.N3TS_P_8LHS']
            # for k in keys_list:
            #     key2 = k + '-' + str(opc_dict['Time'])
            #     value = {
            #     'ts': opc_dict['Time'],
            #     'current': opc_dict[k],
            #     'yname': k,
            #     'pred': {
            #         'mid': 1,
            #         'version': 1,
            #         'value': float(opc_dict[k]) + random.uniform(-1.0, 1.0)
            #        }
            #     }
            #     value = json.dumps(value)
            #     r2.set(key2, value)
            #     r2.expire(key2, 3600)        #设置过期时间为1h
            # del opc_dict['Time']
            # r.set('latest', key)
            # r.hset(key, mapping=opc_dict)
            # r.expire(key, REDIS_EXPIRE_TIME)           #设置过期时间


if __name__ == '__main__':
    # keys = []
    opc_dict = {}
    print(os.getcwd())  # 打印出当前工作路径
    # with open("/workspace/power_model_system/keys.txt", 'r') as f:
    #     keys = f.readlines()
    # keys = ''.join(keys).strip('\n').splitlines()
    keys = list(df.columns)
    print(len(keys))
    r.set('all_points', ','.join(keys))
    r.persist('all_points')
    # keys.insert(0, 'Time')
    timer(keys)
    # write_predict_data()
