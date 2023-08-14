import json
import time
import traceback
import rpyc
from rpyc import Service
from flask_app.apschedule_tasks.point_check import glovar
from flask_app.apschedule_tasks.point_check.point_check import  custom_funcs, update_point_limits
from flask_app.apschedule_tasks.point_check.custom_funcs import *
import re
# 定义 TimeService 类
class PointCheckService(Service):
    def exposed_get_time(self): # 在RPC 调用 名字加 exposed_ 前缀
        return time.ctime()


    def exposed_refresh_pointlimits_from_db(self): # 在RPC 调用 名字加 exposed_ 前缀
        update_point_limits()
        return True

    @staticmethod
    def get_eval(code_str):
        eval_globals = dict()
        eval_globals.update(custom_funcs.__dict__)
        eval_globals.update(glovar.__dict__)
        if code_str and code_str != '':
            return eval(code_str, eval_globals)
        
    def exposed_get_realtime_expect_history(self, point_name, expect_str, history_length):
        expect_history = []
        latest_ts =int(redis.read('latest'))
        start_ts = int(latest_ts) - history_length
        end_ts = int(latest_ts)
        ts_history = list(range(start_ts, end_ts+1))
        
        # 获取历史实时数据
        key_list = ['{}@{}'.format(ts, point_name) for ts in ts_history]
        p_res = redis.redis_client.mget(*key_list)
        realtime_history = list()
        for pv in p_res:
            if pv is not None:
                pv = float(pv)
            realtime_history.append(pv)
        # 获取历史期望值数据
        assert type(glovar.latest_ts) is not str
        for ts in ts_history:
            try:
                
                expect_str_his = re.sub(
                    pattern=r'CDATA\s*\[\s*["\'](.*)["\']\s*\]', 
                    repl=f'float(redis.read("{ts}@\\1"))', 
                    string=expect_str# "CDATA['NDSF.sdfdsf']+5"
                )
                expect_str_his = re.sub(
                pattern=r'yc\(["\']([\w\d.-]+)["\']\)', 
                    repl=f'json.loads(result_redis.read("\\1-regression-{ts}"))["pred"]["value"]', 
                    string=expect_str_his# "CDATA['NDSF.sdfdsf']+5"
                )
                expect_str_his = re.sub(
                pattern=r'yc\s*\(\s*["\']([\w\d.-]+)["\']\s*,\s*["\']([\w]+)["\']\s*\)', 
                    repl=f'json.loads(result_redis.read("\\1-\\2-{ts}"))["pred"]["value"]', 
                    string=expect_str_his# "CDATA['NDSF.sdfdsf']+5"
                )
                expect = self.get_eval(expect_str_his)
            except Exception as e:
                expect_history.append(None)
                continue
            expect_history.append(expect)
        return {
            'point_name': point_name,
            'expect_history':expect_history,
            'realtime_history':realtime_history,
            'ts_history':ts_history
        }
    
    
    def exposed_get_eval(self,code_str):
        return self.get_eval(code_str)
    
    def exposed_get_point_filter(self, point_name,filter_str):
        current = glovar.CDATA[point_name]
        if filter_str and '//' in filter_str:
            tmp_sp = filter_str.split('//')
            
            if tmp_sp[0] == 'FILTER':
                res = FILTER(point_name, int(tmp_sp[1]))
            elif tmp_sp[0] == 'FILTER1':
                res = FILTER1(point_name, int(tmp_sp[1]))
            else:
                res = current
        else:
            res = PointCheckService.get_eval(filter_str)
        return res
    
    # TODO: rpc 接口为None问题
    def exposed_get_CDATA_value(self, point_name: str):
        cdata = json.loads(json.dumps(glovar.CDATA))
        return cdata[point_name]

    def exposed_get_MID_value(self, point_name: str):
        mid = json.loads(json.dumps(glovar.MID))
        return mid[point_name]

    def exposed_get_variance(self, point_name: str, duration:int):
        point_name = rpyc.classic.obtain(point_name)
        duration = rpyc.classic.obtain(duration)

        return variance(point_name, duration)

    def exposed_get_mid_var(self, mid_var_val: str):
        return PointCheckService.get_eval(mid_var_val)

    def exposed_get_eval_offset(self, offset_str: str):
        if offset_str and '//' in offset_str:
            offset_str_list = offset_str.split('//')
            
            high_offset = PointCheckService.get_eval(offset_str_list[0])
            low_offset = PointCheckService.get_eval(offset_str_list[1])
        else:
            high_offset = low_offset = PointCheckService.get_eval(offset_str)
            
        return high_offset, low_offset
    
    
    def exposed_get_realtime_warning_list(self):
        return json.loads(json.dumps(glovar.cached_warnings))
        