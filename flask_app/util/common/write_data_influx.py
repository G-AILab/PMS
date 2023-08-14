import json
import time
from threading import Timer
import collections
import pickle
import os
import sys

from flask_app.util.db.influxDB_util.client import InfluxDBClient
from time_trans import *



ip = '10.0.100.4'
client = InfluxDBClient(host=ip, port=8085, username='root', password='root', database='test')
dq = collections.deque()
dic = {}
dic2 = {}
keys = []

with open("keys.txt", 'r') as f:
    keys = f.readlines()
keys = ''.join(keys).strip('\n').splitlines()

with open('/workspace/data/data-1day.pkl','rb') as file:
    df = pickle.load(file)

for i in range(0,8640):
     dq.append(df.iloc[i])

init_data = df.iloc[0]
for i in range(0,2531):
    dic[keys[i+1]] = init_data[i]
    dic2[keys[i+1]] = init_data[i]

def write_data():
    '''
       将数据以opc服务器发送形式写入influxDB
       ----------
       ----------
       '''
    current_time = int(time.time())
    i = 0
    while i < 86400:
        date = time.strftime("%Y-%m-%d", time.localtime())
        hour = time.strftime("%H", time.localtime())
        data = df.iloc[i % 8640]
        previous_time = current_time
        current_time = int(time.time())
        if current_time - previous_time >= 1:
            if i > 0:
                for j in range(0,2531):
                    if dic[keys[j+1]] == data[j]:
                        if dic2.__contains__(keys[j+1]):
                            del dic2[keys[j+1]]
                    else:
                        dic[keys[j+1]] = data[j]
                        dic2[keys[j+1]] = data[j]
            print(len(dic2))
            t = DT.utcfromtimestamp(float(current_time)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            json_body = [{
                "measurement": "opc_data",
                "tags": {
                    "date": date,
                    "hour": hour
                },
                "time": t,
                "fields": {
                    k : v for k,v in dic2.items()
                }
            }]
            client.write_points(json_body)
            i += 1
            print("write success")

if __name__ == '__main__':
    write_data()
    # print('ok')








