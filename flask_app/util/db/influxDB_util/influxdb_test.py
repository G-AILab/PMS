from cgi import test
import sys
sys.path.insert(0, '/workspace/power_model_system')
from flask_app import influx
from flask_app.util.common.time_trans import *
from flask_app.util.common.file_os import *
import redis
from flask_app.config import get_config
from flask_app.websocket.redis_pub_sub import RedisPub
from flask_app.util.db.influxDB_util.util import InfluxDB
_get_config = get_config()
from memory_profiler import profile
import arrow

sample_step = 2
start_time = Normaltime('2022-02-01 00:00:00')
end_time = Normaltime('2022-02-01 01:00:00')

chunked_influx = InfluxDB(
    host=_get_config.INFLUX_HOST, port=_get_config.INFLUX_PORT,
    username=_get_config.INFLUX_USERNAME, password=_get_config.INFLUX_PASSWORD,
    db=_get_config.INFLUX_DB
)
# @profile
def test_read():
    frames = []
    sec = (arrow.get(end_time) - arrow.get(start_time)).seconds + 1
    chunk_size = 60
    print(chunk_size)
    if sec % sample_step != 0:
        sec //= sample_step
        sec += 1
    else:
        sec //= sample_step
    print(sec)
    chunk_count = 0
    
    t1 = time.time()
    for res in chunked_influx.query(sample_step, start_time, end_time, [], chunked=True, chunk_size=chunk_size):
        # print("chunk:{}".format(len(list(res.get_points()))))
        # if len(list(res.get_points())) == 0:
        #     print(res)
        #     break
        chunk_count += len(list(res.get_points()))
        data = res._raw['series'][0]['values']
        columns = res._raw['series'][0]['columns']
        pdata = pd.DataFrame(data, columns=columns)
        # pdata = pdata.fillna(method='ffill')
        # pdata = pdata.fillna(method='bfill')
        frames.append(pdata)
        print("process:{}%".format(round(chunk_count / sec * 100, 2)))
    t2 = time.time()
    print('query use:',t2-t1)
    result = pd.concat(frames)
    result = result.fillna(method='ffill')
    result = result.fillna(method='bfill')
    t3 = time.time()
    print('concat use:',t3-t2)
    print(result)
    
# test_read()

# print(10 // 100)


    


