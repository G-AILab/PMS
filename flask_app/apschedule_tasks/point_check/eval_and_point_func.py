
import datetime
from inspect import currentframe, getframeinfo
import functools
import json
import traceback
import threading
import time
from typing import Dict, List, Optional, Tuple, Union
from enum import Enum
import loguru
import numpy as np
from flask_app.apschedule_tasks import _get_config, redis, result_redis
from flask_app.apschedule_tasks import app as flask_app
from flask_app.common.send_websocket_msg import send_websocket_msg
from flask_app.models.inter_variable import InterVariable
from flask_app.models.oper_guide_step import OperGuideStep
from flask_app.models.point_desc import PointDesc, ReminderErrorStatus
from flask_app.models.reminder import Reminder
from flask_app.util.json import PowermodelJSONizer
from flask_app.util.log import LoggerPool
from pebble import ThreadPool
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from loguru import logger

from . import glovar 
from . import custom_funcs
import multiprocessing
# from flask_socketio import emit
from .custom_funcs import get_his, init_point_check_env, FILTER, FILTER1
from .glovar import *
from flask_app.util.waitgroup import WaitGroup
from flask_app.apschedule_tasks.point_check.custom_funcs import FILTER, FILTER1

# 多进程不能使用这个 logger 变量
# logger = LoggerPool().get('point_check', file_location='logs/point_check.log')


def handle_step_error(text):
    def decorator(func):
        def wrapper(point_name,*args, **kw):
            try:
                res= func(point_name,*args, **kw)
                return res
            except KeyError as e:
                loguru.logger.warning({
                    "msg": "点名未找到",
                    "point_name": point_name
                })
            
            except Exception as e:
                loguru.logger.warning({
                    "error": e,
                    "trace": traceback.format_exc()
                })
                # logger.warning(f"点名预警错误", extra={
                #     "point_name":point_name,
                #     "step":text,
                #     "error":e
                # })
                return None
        return wrapper
    return decorator

#  滤波的状态
@handle_step_error('点名滤波')
def point_filter(point_name, current,filter_str):
    if filter_str and '//' in filter_str:
        tmp_sp = filter_str.split('//')
        if tmp_sp[0] == 'FILTER':
            res = FILTER(point_name, int(tmp_sp[1]))
        elif tmp_sp[0] == 'FILTER1':
            res = FILTER1(point_name, int(tmp_sp[1]))
        else:
            res = current
    else:
        res = _eval_str_or_default(point_name, filter_str, default_value = current)
    return res
    
@handle_step_error("中间变量执行")    
def mid_var_calc(iv):
    return _eval_str_or_default(iv.var_name, iv.var_value,default_value=iv.var_value)


def _eval_str_or_default(point_name, code_str, default_value,reminder_step_name=''):
    """若 code_str 为空 或执行出错或执行为空，则为 default value 

    Args:
        point_name (str): 点名名
        code_str (str): python 代码
        default_value: 默认值

    Returns:
        _type_: 返回值，若 code_str 为空 或执行为 None，则为 default value 
    """
    res = _eval_str(point_name,code_str,reminder_step_name=reminder_step_name)      
    if res is None:
        # plogger.info(f'计算出错，清检查值是否为空或输错代码，使用默认值: {default_value} ')
        res = default_value
    return res



def _eval_str(point_name, code_str,reminder_step_name=''):
    eval_globals = dict()
    eval_globals.update(custom_funcs.__dict__)
    eval_globals.update(glovar.__dict__.copy())
    res = None
    code_str = str(code_str)
    if code_str and code_str != '':
        try:
            res = eval(code_str, eval_globals)
        except Exception as e:
            # logger.warning("点名eval错误", extra={
            #     "step":reminder_step_name,
            #     "point_name": point_name,
            #     "code_str":code_str,
            #     "error":e,
            # })
            pass
    return res




@handle_step_error('判断期望值，偏差值是否满足条件')
def judge_expect(point_name, current, expect_str, offset_str, upper_value, lower_value, unit, latest_ts):
    assert unit is not None
    # global create_cold_redis
    # 若用户未填写expect字段，则默认为取预测值作为expect
    if expect_str is None or len(expect_str) == 0:
        expect_str = "yc('{}')".format(point_name)

    expect = _eval_str(point_name, expect_str,'judge_expect_expect')
    websocket_res = {
                    'ts': latest_ts,
                    # 'current': data.loc[data.shape[0] - 1, yname],
                    'current': float(current) if current else None,
                    'point_name': point_name,
                    'expect': expect
        }
    send_websocket_msg('point_check_expect',data=websocket_res, room=unit)
    websocket_res['unit'] = unit
    # create_cold_redis.append(websocket_res)
    if not (isinstance(expect, float) or isinstance(expect, int)):  # 若expect不是float或int，则无法进行下一步判断
        return None, None, None, None,expect

    if offset_str and '//' in offset_str:
        offset_str_list = offset_str.split('//')
        
        high_offset = _eval_str(point_name, offset_str_list[0],'judge_expect_high_offset')
        low_offset = _eval_str(point_name, offset_str_list[1],'judge_expect_low_offset')
    else:
        high_offset = low_offset = _eval_str(point_name, offset_str,'judge_expect_offset_str')
    websocket_res = {
                    'ts': latest_ts,
                    # 'current': data.loc[data.shape[0] - 1, yname],
                    'current': float(current) if current else None,
                    'point_name': point_name,
                    'high_offset': high_offset,
                    'low_offset': low_offset
        }
    send_websocket_msg('point_check_offset',data=websocket_res, room=unit)
    websocket_res['unit'] = unit
    # create_cold_redis.append(websocket_res)
    # try:
    high_limit = expect + high_offset if high_offset else None
    low_limit = expect - low_offset if low_offset else None
    if high_limit is not None and upper_value is not None:
        high_limit = min(high_limit, upper_value)
    if low_limit is not None and lower_value is not None:
        low_limit = max(low_limit, lower_value)
    

    over_flag = high_limit is not None and (current > high_limit)
    below_flag = low_limit is not None and (current < low_limit)
    return over_flag, below_flag, high_limit, low_limit, expect

@handle_step_error('判断方差是否满足条件')
def judge_variance(point_name: str, duration_str: str, gate_str: str, latest_ts: int):
    duration = _eval_str(point_name, duration_str,'judge_variance_duration')
    gate = _eval_str(point_name, gate_str,'judge_variance_gate')
    if not duration or not gate:
        return None, None, None, None, None

    # start_ts = ts - duration
    # with redis.redis_client.pipeline() as p:
    #     for i in range(duration):
    #         p.hmget(str(start_ts + i), point_name)
    #     res_list = p.execute()
    
    duration_values = get_his(point_name, [0,duration])
    duration_variance = np.var(duration_values)
    is_zero = duration_variance == 0
    is_over = duration_variance > gate
    return is_zero, is_over, duration, duration_variance, gate



def check_config(code_str):
    if code_str == '' or code_str is None:
        return False
    return True

@handle_step_error('点检查')
def judge_point_old(point_name,pid , realtime, **kwargs ) -> Dict:
    # current 为滤波后的值
    latest_ts = kwargs.get('latest_ts')
    switch_str = kwargs.get('switch')
    filter_str = kwargs.get('filter_str')
    desc = kwargs.get('desc')
    unit = kwargs.get('unit')
    origin_all_status = kwargs.get('all_status')
    current_warning_list = kwargs.get('current_warning_list')
    first_warning_list = list()
    
    
    # 滤波
    current = point_filter(point_name, realtime, filter_str) # FILTER 滤波时有可能出错 ValueError: zero-size array to reduction operation maximum which has no identity
    websocket_res = {
                'ts': latest_ts,
                # 'current': data.loc[data.shape[0] - 1, yname],
                'current': float(current) if current else None,
                'point_name': point_name,
                'actual': current
    }
    send_websocket_msg('point_check_actual',data=websocket_res, room=unit)
    
    expect = _eval_str(point_name, kwargs.get('expect'),'judge_expect_expect')
    if origin_all_status is None or origin_all_status == '' or origin_all_status == {}:
        origin_all_status = {
            'switch' : ReminderErrorStatus.NORMAL,
            'upper' : ReminderErrorStatus.NORMAL,
            'lower' : ReminderErrorStatus.NORMAL,
            'expect_over' : ReminderErrorStatus.NORMAL,
            'expect_below' : ReminderErrorStatus.NORMAL,
            'variance_zero' : ReminderErrorStatus.NORMAL,
            'variance_over' : ReminderErrorStatus.NORMAL,
        }
    all_status = {
        'switch' : ReminderErrorStatus.NORMAL,
        'upper' : ReminderErrorStatus.NORMAL,
        'lower' : ReminderErrorStatus.NORMAL,
        'expect_over' : ReminderErrorStatus.NORMAL,
        'expect_below' : ReminderErrorStatus.NORMAL,
        'variance_zero' : ReminderErrorStatus.NORMAL,
        'variance_over' : ReminderErrorStatus.NORMAL,
    }
    # 检查是否配置
    # if check_config(switch_str):
    #     logger.info(f"未配置触发条件，进行检查", extra={
    #         "point_name": point_name,
    #     })
    switch = _eval_str(point_name, switch_str,'switch')
    websocket_res = {
                    'ts': latest_ts,
                    # 'current': data.loc[data.shape[0] - 1, yname],
                    'current': float(current) if current else None,
                    'point_name': point_name,
                    'switch': bool(switch),
    }
    send_websocket_msg('point_check_switch',data=websocket_res, room=unit)
    websocket_res['unit'] = unit


    if switch_str and (switch is False  or switch == 0):
        # 若存在触发条件且触发条件不满足（不为1）则不报警
        all_status['switch'] = ReminderErrorStatus.NORMAL # 不检查
        return {
            'pid': pid,
            'point_name': point_name,
            'warnings': list(),
            'first_warning_list': first_warning_list,
            'all_status': all_status,
            'status_changed':compareStatus(all_status, origin_all_status)
        }
    all_status['switch'] = ReminderErrorStatus.ERROR # 检查

    warning_list = list()
    first_warning_list = list()
    # 判断上上限
    upper = _eval_str(point_name, kwargs.get('upper'),'upper')
    websocket_res = {
                    'ts': latest_ts,
                    'current': current,
                    'point_name': point_name,
                    'upper': upper
    }
    send_websocket_msg('point_check_upper',data=websocket_res, room=unit)
    websocket_res['unit'] = unit
    ex_upper = False
    if upper is not None and current > upper:
        ex_upper = True
        fist_report_flag,first_report_ts =  first_report_judge(current_warning_list, all_status, origin_all_status, latest_ts,'upper')
        res = {
            'type': 'upper',
            'first_report_ts': first_report_ts,
            'msg': format_msg_json(point_name, desc, '高高报警', round(realtime,3), expect, upper,extra='{} {} 高高报警，实时值 {} 超出上上限 {}'.format(point_name, desc,round(current,3), upper)),
            # 'msg': '{} {} 高高报警，实时值 {} 超出上上限 {}'.format(point_name, desc,round(current,3), upper),
            'first_report_flag' : fist_report_flag,
            'unit':unit
        }
        if fist_report_flag:
            first_warning_list.append(res)
        # logger.warning("实时值超出上限", extra={
        #     "point_name":point_name,
        #     "current":current,
        #     "upper":upper
        # })
        warning_list.append(res)
    else:
        # logger.info("实时值上上限检查通过", extra={
        #     "current":current,
        #     "upper":upper
        # })
        all_status['upper'] = ReminderErrorStatus.NORMAL

    # 判断下下限
    ex_lower = False
    lower = _eval_str(point_name, kwargs.get('lower'),'lower')
    websocket_res = {
                    'ts': latest_ts,
                    'current': current,
                    'point_name': point_name,
                    'lower': lower
    }
    send_websocket_msg('point_check_lower',data=websocket_res, room=unit)
    websocket_res['unit'] = unit
    if lower is not None and current < lower: 
        first_report_flag,first_report_ts =  first_report_judge(current_warning_list, all_status, origin_all_status, latest_ts,'lower')
        res = {
            'type': 'lower',
            'first_report_ts': first_report_ts,
            'msg': format_msg_json(point_name, desc, '低低报警', round(realtime,3), expect, lower, extra='{} {} 实时值 低低报警 {} 低于下下限 {}'.format(point_name, desc,round(current,3), lower)),
            'first_report_flag' : first_report_flag,
            'unit':unit
        }
        ex_lower = True
        # plogger.error(f"错误：实时值:{current}，超出下下限:{lower}")
        all_status['lower'] = ReminderErrorStatus.ERROR
        # 如果原来不是error，那么就是第一次error
        if first_report_flag:
            first_warning_list.append(res)
        warning_list.append(res)
    else:
        # plogger.info(f"检查通过，实时值:{current}，高于下下限:{lower}")
        all_status['lower'] = ReminderErrorStatus.NORMAL

    # 判断期望值偏差上下限
    over, below, high_limit, low_limit, expect = judge_expect(point_name, current, kwargs.get('expect'), kwargs.get('offset'), upper, lower, unit=unit, latest_ts=latest_ts)
    if not ex_upper and over:
        first_report_flag,first_report_ts =  first_report_judge(current_warning_list, all_status, origin_all_status, latest_ts,'expect_over')

        res ={ 
            'type': 'expect_over',
            'first_report_ts': first_report_ts,
            'msg': format_msg_json(point_name, desc, '高报警', round(realtime,3), expect, high_limit,extra='{} {} 高报警 实时值 {} 超出期望偏差上限 {}'.format(point_name , desc, round(current,3), high_limit)),
            'first_report_flag' : first_report_flag,
            'unit':unit
        }
        if first_report_flag:
            first_warning_list.append(res)

        all_status['expect_over'] = ReminderErrorStatus.ERROR
        warning_list.append(res)
    else:
        all_status['expect_over'] = ReminderErrorStatus.NORMAL
        
    if not ex_lower and below:
        first_report_flag,first_report_ts =  first_report_judge(current_warning_list, all_status, origin_all_status, latest_ts,'expect_below')
        res = {
            'type': 'expect_below',
            'first_report_ts':first_report_ts,
            'msg': format_msg_json(point_name, desc, '低报警', round(realtime,3), expect, low_limit,extra='{} {} 低报警， 实时值 {} 低于期望偏差下限 {}'.format(point_name, desc, round(current,3), low_limit)),
            'first_report_flag' : first_report_flag,
            'unit':unit
        }
        all_status['expect_below'] = ReminderErrorStatus.ERROR
        if first_report_flag:
            first_warning_list.append(res)
        warning_list.append(res)
    else:
        all_status['expect_below'] = ReminderErrorStatus.NORMAL
    # 判断方差
    is_zero, is_over, duration,variance,gate  = judge_variance(point_name, kwargs.get('v_duration'), kwargs.get('v_gate'), kwargs.get('latest_ts'))
    websocket_res = {
                    'ts': latest_ts,
                    'current': current,
                    'duration': duration,
                    'gate': gate,
                    'point_name': point_name,
                    'variance': variance
    }
    send_websocket_msg('point_check_variance',data=websocket_res, room=unit)
    websocket_res['unit'] = unit
    if is_zero:
        first_report_flag,first_report_ts =  first_report_judge(current_warning_list, all_status, origin_all_status, latest_ts,'variance_zero')
        res = {
            'type': 'variance_zero',
            'first_report_ts': first_report_ts,
            'msg': format_msg_json(point_name, desc, '坏点',  realtime, expect, None, extra=f'过去{duration}秒内，方差为 0'),
            'first_report_flag' : first_report_flag,
            'unit':unit
            
        }
        # logger.warning('错误：过去{}秒内，方差为 0'.format(duration))
        all_status['variance_zero'] = ReminderErrorStatus.ERROR
        if first_report_flag:
            first_warning_list.append(res)
        warning_list.append(res)
    else:
        # plogger.info('检查通过：过去{}秒内，方差不为0'.format( duration))
        all_status['variance_zero'] = ReminderErrorStatus.NORMAL
        
    if is_over:
        first_report_flag,first_report_ts =  first_report_judge(current_warning_list, all_status, origin_all_status, latest_ts,'variance_over')
        res = {
            'type': 'variance_over',
            'first_report_ts': first_report_ts,
            'msg': format_msg_json(point_name, desc, '波动大', variance, expect, gate, extra=f'过去{duration}秒内，方差超出设定值'),
            'first_report_flag' : first_report_flag,
            'unit':unit
            
        }
        # logger.warning('错误：过去{}秒内，方差 {} 超出设定值 {}'.format(duration,variance,gate))
        # 如果原来不是error，那么就是第一次error
        all_status['variance_over'] = ReminderErrorStatus.ERROR
        if first_report_flag:
            first_warning_list.append(res)
        warning_list.append(res)
    else:
        # plogger.info('检查通过：过去{}秒内，方差 {} 在设定值范围内'.format(duration,variance))
        all_status['variance_over'] = ReminderErrorStatus.NORMAL
        
    return {
        'pid': pid,
        'point_name': point_name,
        'warnings': warning_list,
        'first_warning_list': first_warning_list,
        'all_status': all_status,
        'status_changed':compareStatus(all_status, origin_all_status)
    }















@handle_step_error('点检查')
def judge_point(point_limit: PointDesc, realtime: float, latest_ts:int, point_status:Optional[Dict[str, int]], point_warnings_list) -> Dict:
    # current 为滤波后的值
    # latest_ts = kwargs.get('latest_ts')
    point_name = point_limit.point_name
    switch_str = point_limit.switch
    filter_str = point_limit.actual
    desc = point_limit.describe
    unit = point_limit.unit
    
    origin_all_status = point_status
    current_warning_list = point_warnings_list
    
    first_warning_list = list()
    
    
    # 滤波
    current = point_filter(point_name, realtime, filter_str) # FILTER 滤波时有可能出错 ValueError: zero-size array to reduction operation maximum which has no identity
    websocket_res = {
                'ts': latest_ts,
                # 'current': data.loc[data.shape[0] - 1, yname],
                'current': float(current) if current else None,
                'point_name': point_name,
                'actual': current
    }
    send_websocket_msg('point_check_actual',data=websocket_res, room=unit)
    expect = _eval_str(point_name,point_limit.expect,'judge_expect_expect')
    if origin_all_status is None or origin_all_status == '' or origin_all_status == {}:
        origin_all_status = {
            'switch' : ReminderErrorStatus.NORMAL,
            'upper' : ReminderErrorStatus.NORMAL,
            'lower' : ReminderErrorStatus.NORMAL,
            'expect_over' : ReminderErrorStatus.NORMAL,
            'expect_below' : ReminderErrorStatus.NORMAL,
            'variance_zero' : ReminderErrorStatus.NORMAL,
            'variance_over' : ReminderErrorStatus.NORMAL,
        }
    all_status = {
        'switch' : ReminderErrorStatus.NORMAL,
        'upper' : ReminderErrorStatus.NORMAL,
        'lower' : ReminderErrorStatus.NORMAL,
        'expect_over' : ReminderErrorStatus.NORMAL,
        'expect_below' : ReminderErrorStatus.NORMAL,
        'variance_zero' : ReminderErrorStatus.NORMAL,
        'variance_over' : ReminderErrorStatus.NORMAL,
    }
    switch = _eval_str(point_name, switch_str,'switch')
    websocket_res = {
                    'ts': latest_ts,
                    # 'current': data.loc[data.shape[0] - 1, yname],
                    'current': float(current) if current else None,
                    'point_name': point_name,
                    'switch': bool(switch),
    }
    send_websocket_msg('point_check_switch',data=websocket_res, room=unit)
    websocket_res['unit'] = unit


    if switch_str and (switch is False  or switch == 0):
        # 若存在触发条件且触发条件不满足（不为1）则不报警
        all_status['switch'] = ReminderErrorStatus.NORMAL # 不检查
        return {
            'pid': point_limit.pid,
            'point_name': point_name,
            'warnings': list(),
            'first_warning_list': first_warning_list,
            'all_status': all_status,
            'status_changed':compareStatus(all_status, origin_all_status)
        }
    all_status['switch'] = ReminderErrorStatus.ERROR # 检查

    warning_list = list()
    first_warning_list = list()
    # 判断上上限
    upper = _eval_str(point_name, point_limit.upper_limit,'upper')
    websocket_res = {
                    'ts': latest_ts,
                    'current': current,
                    'point_name': point_name,
                    'upper': upper
    }
    send_websocket_msg('point_check_upper',data=websocket_res, room=unit)
    websocket_res['unit'] = unit
    ex_upper = False
    if upper is not None and current > upper:
        ex_upper = True
        fist_report_flag,first_report_ts =  first_report_judge(current_warning_list, all_status, origin_all_status, latest_ts,'upper')
        res = {
            'type': 'upper',
            'first_report_ts': first_report_ts,
            'msg': format_msg_json(point_name, desc, '高高报警', round(realtime,3), expect, upper,extra='{} {} 高高报警，实时值 {} 超出上上限 {}, 历史值: {}'.format(point_name, desc,round(current,3), upper,get_his(point_name, [0, 300]))),
            # 'msg': '{} {} 高高报警，实时值 {} 超出上上限 {}'.format(point_name, desc,round(current,3), upper),
            'first_report_flag' : fist_report_flag,
            'unit':unit
        }
        if fist_report_flag:
            first_warning_list.append(res)
        warning_list.append(res)
    else:
        all_status['upper'] = ReminderErrorStatus.NORMAL

    # 判断下下限
    ex_lower = False
    lower = _eval_str(point_name, point_limit.lower_limit,'lower')
    websocket_res = {
                    'ts': latest_ts,
                    'current': current,
                    'point_name': point_name,
                    'lower': lower
    }
    send_websocket_msg('point_check_lower',data=websocket_res, room=unit)
    websocket_res['unit'] = unit
    if lower is not None and current < lower: 
        first_report_flag,first_report_ts =  first_report_judge(current_warning_list, all_status, origin_all_status, latest_ts,'lower')
        res = {
            'type': 'lower',
            'first_report_ts': first_report_ts,
            'msg': format_msg_json(point_name, desc, '低低报警', round(realtime,3), expect, lower, extra='{} {} 实时值 低低报警 {} 低于下下限 {}, 历史值: {}'.format(point_name, desc,round(current,3), lower, get_his(point_name, [0, 300]))),
            'first_report_flag' : first_report_flag,
            'unit':unit
        }
        ex_lower = True
        # plogger.error(f"错误：实时值:{current}，超出下下限:{lower}")
        all_status['lower'] = ReminderErrorStatus.ERROR
        # 如果原来不是error，那么就是第一次error
        if first_report_flag:
            first_warning_list.append(res)
        warning_list.append(res)
    else:
        # plogger.info(f"检查通过，实时值:{current}，高于下下限:{lower}")
        all_status['lower'] = ReminderErrorStatus.NORMAL

    # 判断期望值偏差上下限
    over, below, high_limit, low_limit, expect = judge_expect(point_name, current,point_limit.expect, point_limit.offset, upper, lower, unit=unit, latest_ts=latest_ts)
    if not ex_upper and over:
        first_report_flag,first_report_ts =  first_report_judge(current_warning_list, all_status, origin_all_status, latest_ts,'expect_over')
        
        res ={ 
            'type': 'expect_over',
            'first_report_ts': first_report_ts,
            'msg': format_msg_json(point_name, desc, '高报警', round(realtime,3), expect, high_limit,extra='{} {} 高报警 实时值 {} 超出期望偏差上限 {}, 历史值: {}'.format(point_name , desc, round(current,3), high_limit, get_his(point_name, [0, 300]))),
            'first_report_flag' : first_report_flag,
            'unit':unit
        }
        all_status['expect_over'] = ReminderErrorStatus.ERROR
        warning_list.append(res)
    else:
        all_status['expect_over'] = ReminderErrorStatus.NORMAL
        
    if not ex_lower and below:
        first_report_flag,first_report_ts =  first_report_judge(current_warning_list, all_status, origin_all_status, latest_ts,'expect_below')
        res = {
            'type': 'expect_below',
            'first_report_ts':first_report_ts,
            'msg': format_msg_json(point_name, desc, '低报警', round(realtime,3), expect, low_limit,extra='{} {} 低报警， 实时值 {} 低于期望偏差下限 {}, 历史值: {}'.format(point_name, desc, round(current,3), low_limit, get_his(point_name, [0, 300]))),
            'first_report_flag' : first_report_flag,
            'unit':unit
        }
        all_status['expect_below'] = ReminderErrorStatus.ERROR
        if first_report_flag:
            first_warning_list.append(res)
        warning_list.append(res)
    else:
        all_status['expect_below'] = ReminderErrorStatus.NORMAL
    # 判断方差
    is_zero, is_over, duration,variance,gate  = judge_variance(point_name, point_limit.variance_duration, point_limit.variance_gate, latest_ts)
    websocket_res = {
                    'ts': latest_ts,
                    'current': current,
                    'duration': duration,
                    'gate': gate,
                    'point_name': point_name,
                    'variance': variance
    }
    send_websocket_msg('point_check_variance',data=websocket_res, room=unit)
    websocket_res['unit'] = unit
    if is_zero:
        first_report_flag,first_report_ts =  first_report_judge(current_warning_list, all_status, origin_all_status, latest_ts,'variance_zero')
        res = {
            'type': 'variance_zero',
            'first_report_ts': first_report_ts,
            'msg': format_msg_json(point_name, desc, '坏点',  realtime, expect, None, extra=f'过去{duration}秒内，方差为 0'),
            'first_report_flag' : first_report_flag,
            'unit':unit
            
        }
        # logger.warning('错误：过去{}秒内，方差为 0'.format(duration))
        all_status['variance_zero'] = ReminderErrorStatus.ERROR
        if first_report_flag:
            first_warning_list.append(res)
        warning_list.append(res)
    else:
        # plogger.info('检查通过：过去{}秒内，方差不为0'.format( duration))
        all_status['variance_zero'] = ReminderErrorStatus.NORMAL
        
    if is_over:
        first_report_flag,first_report_ts =  first_report_judge(current_warning_list, all_status, origin_all_status, latest_ts,'variance_over')
        res = {
            'type': 'variance_over',
            'first_report_ts': first_report_ts,
            'msg': format_msg_json(point_name, desc, '波动大', variance, expect, gate, extra=f'过去{duration}秒内，方差超出设定值'),
            'first_report_flag' : first_report_flag,
            'unit':unit
            
        }
        # logger.warning('错误：过去{}秒内，方差 {} 超出设定值 {}'.format(duration,variance,gate))
        # 如果原来不是error，那么就是第一次error
        all_status['variance_over'] = ReminderErrorStatus.ERROR
        if first_report_flag:
            first_warning_list.append(res)
        warning_list.append(res)
    else:
        # plogger.info('检查通过：过去{}秒内，方差 {} 在设定值范围内'.format(duration,variance))
        all_status['variance_over'] = ReminderErrorStatus.NORMAL
        
    return {
        'pid': point_limit.pid,
        'point_name': point_name,
        'warnings': warning_list,
        'first_warning_list': first_warning_list,
        'all_status': all_status,
        'status_changed':compareStatus(all_status, origin_all_status)
    }















def compareStatus(s1, s2):
    for k in s1:
        if s1[k] != s2[k]:
            return True
    return False



def current_warning_fetch(warning_list, warning_type):
    # 从warning_list 中获取指定的warning ， 不存在返回None
    for warning in warning_list:
        if warning['type'] == warning_type:
            return warning
    return None
            

def first_report_judge(current_warning_list:List , all_status: Dict [str, ReminderErrorStatus],origin_all_status: Dict [str, ReminderErrorStatus],
                       latest_ts: int, warning_type : str):
    first_report_ts = latest_ts
    first_report_flag = False
    all_status[warning_type] = ReminderErrorStatus.ERROR
    # 如果原来不是error，那么就是第一次error
    if origin_all_status[warning_type] is not ReminderErrorStatus.ERROR:
        first_report_flag = True
    else:
        # 不是第一次error
        warning = current_warning_fetch(current_warning_list,warning_type)
        assert warning is not None,f"{ current_warning_list}, {warning_type}"
        if 'first_report_ts'  in warning:
            first_report_ts = warning['first_report_ts']
        else:
            warning['first_report_ts'] = latest_ts
    return first_report_flag, first_report_ts
        
def format_msg_json(pname, pvalue, tp, actual, expect, limit, extra=None):
    return {
        'point_name': pname,
        'point_value': pvalue,
        'type': tp,
        'actual': None if np.isnan(actual) else actual,
        'expect': expect,
        'limit': limit,
        'extra_info': extra
    }




