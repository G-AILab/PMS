import json
from math import nan
import re
import traceback
import time
import loguru
import rpyc
import numpy as np
from flask_app import redis, result_redis

# rpyc 同一条连接连接有多进程问题（疑似是锁，所以都要用不同的连接）
PORT = 18871
# aps_rpc = rpyc.connect("localhost", PORT,config={'sync_request_timeout': 6}, keepalive=True)


def reconnect(func):
    def wrapper(*args, **kw):
        try:
            return func(*args, **kw)
        except EOFError as e:
            global aps_rpc
            aps_rpc = rpyc.connect("localhost", PORT,config={'sync_request_timeout': 6}, keepalive=True)
            return func(*args, **kw)
    return wrapper


def handle_error(func):
    def wrapper(*args, **kw):
        try:
            return func(*args, **kw)
        except EOFError as e:
            global aps_rpc
            aps_rpc = rpyc.connect("localhost", PORT)
            try:
                return func(*args, **kw)
            except Exception as e: # eval_offset
                return str(traceback.format_exc())
        except KeyError as e: # eval_offset
            return f'点名 {str(e.args[0])} 未找到，代码执行错误'
        except Exception as e: # eval_offset
            return str(traceback.format_exc())
    return wrapper


@reconnect
def point_check_eval(code_str:str):
    aps_rpc = rpyc.connect("localhost", PORT,config={'sync_request_timeout': 5})
    res = aps_rpc.root.get_eval(str(code_str))
    # 因为库和 flask 的jsonify 有冲突，必须按类型强转
    if isinstance(res, float):
        return float(res)
    elif isinstance(res, str):
        return str(res)
    elif isinstance(res, list):
        return list(res)
    return res if res is not None else None
# @reconnect
def point_check_filter_eval(point_name, code_str:str):
    aps_rpc = rpyc.connect("localhost", PORT,config={'sync_request_timeout': 5})
    res =  aps_rpc.root.get_point_filter(point_name,str(code_str))
    return float(res) if res is not None else None

def point_check_offset_eval( code_str:str):
    aps_rpc = rpyc.connect("localhost", PORT,config={'sync_request_timeout': 5})
    upper_offset , lower_offset = aps_rpc.root.get_eval_offset(str(code_str))
    return f"{upper_offset}//{lower_offset}"


def inter_var_eval_val_or_error(code_str:str):
    return point_check_eval_val_or_error(str(code_str))

@handle_error
def point_check_eval_val_or_error(code_str:str):
    aps_rpc = rpyc.connect("localhost", PORT,config={'sync_request_timeout': 5})
    res = aps_rpc.root.get_eval(str(code_str))
    if str(res) == 'nan':
        return 'NaN'
    if isinstance(res, float):
        return float(res)
    elif isinstance(res, str):
        return str(res)
    elif isinstance(res, list):
        return list(res)
    elif res == np.NaN or nan:
        return 'NaN'
    return res if res is not None else None

    # return float(res) if res is not None else None

@handle_error
def point_check_filter_val_or_error(point_name, code_str:str):
    aps_rpc = rpyc.connect("localhost", PORT,config={'sync_request_timeout': 1})
    res =  aps_rpc.root.get_point_filter(point_name, str(code_str))  # 不加float json.dumps 会报错
    if isinstance(res, float):
        return float(res)
    elif isinstance(res, str):
        return str(res)
    elif isinstance(res, list):
        return list(res)
    return res if res is not None else None
    # return float(res) if res is not None else None


@handle_error
def point_check_eval_offset_or_error(code_str):
    aps_rpc = rpyc.connect("localhost", PORT,config={'sync_request_timeout': 5})
    upper_offset , lower_offset = aps_rpc.root.get_eval_offset(str(code_str))
    return f"{upper_offset}//{lower_offset}"


@reconnect
def point_check_realtime_warning_list():
    aps_rpc = rpyc.connect("localhost", PORT,config={'sync_request_timeout': 5})
    return aps_rpc.root.get_realtime_warning_list()


@reconnect 
def point_check_get_MID_value(mid_point_name):
    aps_rpc = rpyc.connect("localhost", PORT,config={'sync_request_timeout': 5})
    return aps_rpc.root.get_MID_value(mid_point_name)
    
    
@reconnect 
def point_check_get_CDATA_value(mid_point_name):
    aps_rpc = rpyc.connect("localhost", PORT,config={'sync_request_timeout': 5})
    return aps_rpc.root.get_CDATA_value(mid_point_name)
    
    


@reconnect 
def point_check_get_variance(point_name, duration):
    aps_rpc = rpyc.connect("localhost", PORT,config={'sync_request_timeout': 5})
    return aps_rpc.root.get_variance(point_name, duration)
    


@reconnect 
def point_check_get_realtime_expect_history(point_name, code_str, history_length):
    aps_rpc = rpyc.connect("localhost", PORT,config={'sync_request_timeout': 5})
    json_str = aps_rpc.root.get_realtime_expect_history( point_name, code_str, history_length)
    return eval(str(json_str))
    
