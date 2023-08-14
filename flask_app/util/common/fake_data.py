from cmath import isnan
import redis
import time
import collections
import pickle
import os
import random
import pandas as pd
from  flask_app.websocket.redis_pub_sub import redis_pub, RedisPub
import pymysql
from iapws import iapws97
from iapws import IAPWS97
import numpy as np
from  loguru  import logger
# from flask_app import get_config
import json
import math

ip = 'redis'
port = 6379
REDIS_EXPIRE_TIME = 300  # 插入的数据的过期时间

r = redis.Redis(host=ip, port=port, db=0, decode_responses=True)
websocket_pub = RedisPub(r)
# r2 = redis.Redis(host=ip, port=3377, db=1, decode_responses=True)
# dq = collections.deque()

#client.create_retention_policy('awesome_policy', '105w', 1, default=True)

MID = {}
CDATA = {}
#------------------------------------------自定义函数------------------------------------------------------------------
def Sfunline(A,B):#折线函数
    C= len(B)
    n=int(C/2)
    m=int(C/2-1)
    a=np.zeros(m)
    b=np.zeros(m)
    X=np.zeros(n)
    Y=np.zeros(n)
    if A<=B[0] or A>=B[-2]:
        optimal = B[1] if A<B[0] else B[-1]
    else :
        for i in range (n):
            X[i]=B[i*2]
            Y[i]=B[i*2+1]
        for i in range( m ) :
            a[i] =(Y[i+1] -Y[i]) / (X[i+1] -X[i])
            b[i] =Y[i]-X[i]*a[i]
        for i in range ( m ):
            if A>=X[i] and A<X[i+1]:
                optimal = A*a[i]+b[i]
    return (optimal)

def PackRE(pointname,bite):#打包点解析，点名，第几位
    strPackname= bin(int(CDATA[pointname]))
    # print(Currentdata[pointname], pointname,strPackname)
    Packbite=len(strPackname)-1-bite
    if len(strPackname)<=bite:
        Packdata=0
    else :
        Packdata =strPackname[Packbite]
    return (Packdata)    
#------------------------------------------自定义函数------------------------------------------------------------------


# with open('/workspace/data/test_2_day_1647868301.pickle','rb') as f:
#     df = pickle.load(f)
# df = pd.read_parquet('/workspace/data/异常检测测试_1654053139.parquet')
# df = pd.read_pickle('/workspace/data/test_2_day_1_1648206618.pickle')
df = pd.read_parquet('/workspace/data/all_points_6_1666160524.parquet')
if 'time' in df:
    df = df.drop(['time'], axis=1)
if 'Time' in df:
    df = df.drop(['Time'], axis=1)

# for i in range(min(df.shape[0], 86400)):
#     dq.append(df.iloc[i])

def timer(keys):
    '''
    定时写入redis（每秒）
    ----------
    ----------
    '''
    current_time = int(time.time())
    previous_time = current_time
    current_idx = 0
    while True:
        
        db = pymysql.connect(
         host='mysql',
         port=3306,
         user='root',
         passwd='root',
         db ='power_model',
         charset='utf8'
         )
        # 使用cursor()方法创建一个游标对象cursor
        cursor = db.cursor()
        inter_variables = []
        # SQL 查询语句
        sql = "SELECT * FROM inter_variable" 
        try:
            # 执行SQL语句
            cursor.execute(sql)
            # 获取所有记录列表
            results = cursor.fetchall()
            for row in results:
                inter_variables.append({'var_name': row[1], 'var_value': row[2]})
        except:
            print ("Error: unable to fetch data")

        db.close()
        
        previous_time = current_time
        current_time = int(time.time())
        if current_time - previous_time >= 1:
            # series = dq.popleft()
            series = df.iloc[current_idx]
            # print(series[0])
            key_values = [('{}@{}'.format(current_time, keys[i]), series[i]) for i in range(len(keys))]
            for i in range(len(keys)):
                if math.isnan(series[i]):
                    CDATA.update({keys[i]: None})
                else:
                    CDATA.update({keys[i]: float(series[i])})
            for iv in inter_variables:
                point_name = iv['var_name']
                code_str = iv['var_value']
                if code_str and code_str != '' and code_str[0] != '[':
                    try:
                        res = eval(code_str)
                        MID[point_name] = res
                        print("inter:", point_name, res)
                        key_values.append(('{}@{}'.format(current_time, point_name), res))
                        if math.isnan(res):
                            logger.warning("point {point_name} is nan after calculation")
                            CDATA[point_name] = None
                        else:
                            CDATA[point_name] = float(res)
                    except KeyError as e:
                        logger.warning('point: {} "{}" exec error! {} not found'.format(point_name, code_str, e))
                    except Exception as e:
                        logger.warning('point: {} "{}" exec error! e: {}'.format(point_name, code_str, e))
                    
            with r.pipeline(transaction=False) as p:
                for key, value in key_values:
                    p.setex(key, REDIS_EXPIRE_TIME, float(value))
                CDATA['latest'] = current_time
                print(redis_pub.publish_realtime('1', CDATA))
                # print(CDATA['latest'])
                # print(redis_pub.publish_realtime('2', CDATA))
                # print(redis_pub.publish_realtime('3', CDATA))
                # print(redis_pub.publish_realtime('4', CDATA))
                p.set('latest', current_time)
                p.execute()
            # r.set('latest', str(current_time))
            logger.info(current_time)
            current_idx += 1
            if current_idx >= min(df.shape[0], 86400):
                current_idx = 0

            # for i in range(len(keys)):
            #     if (i == 0):
            #         opc_dict[keys[0]] = current_time
            #         print(current_time)
            #     else:
            #         opc_dict[keys[i]] = series[i-1]
            # dq.popleft()

            # dq.append(series)

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
