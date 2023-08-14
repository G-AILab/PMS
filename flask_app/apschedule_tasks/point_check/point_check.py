from dataclasses import dataclass
import datetime
from inspect import currentframe, getframeinfo
import functools
import json
import os
import traceback
import threading
import time
from typing import Dict, List, Tuple, Union
from enum import Enum
import loguru
import numpy as np
from flask_app.apschedule_tasks import _get_config, redis, result_redis
from flask_app.apschedule_tasks import app as flask_app, t_app , guide_app
# from flask_app.apschedule_tasks.point_check.batch_judge_point import batch_judge_point_process
from flask_app.apschedule_tasks.point_check.eval_and_point_func import _eval_str, judge_point, judge_point_old,handle_step_error
from flask_app.common.send_websocket_msg import send_websocket_msg
from flask_app.models.inter_variable import InterVariable
from flask_app.models.oper_guide_step import OperGuideStep
from flask_app.models.point_desc import PointDesc, ReminderErrorStatus
from flask_app.models.reminder import Reminder
from flask_app.util.json import PowermodelJSONizer
from flask_app.util.log import LoggerPool
from pebble import ThreadPool
from multiprocessing.pool import Pool
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from . import glovar
from . import custom_funcs
import multiprocessing
from .custom_funcs import get_his, init_point_check_env, FILTER, FILTER1
from .glovar import *



points_status :Dict[str, Dict[str, int]] = dict()
points_warning_list: Dict[str, List] = dict()
point_judge_pool: Pool = None
point_check_round = 0
point_limits :List[PointDesc] = list()
all_guide_steps = dict()
CDATA = dict()
realtime_values = dict()


# 保存统计数据
stats_map = {}

# 注意不能在 fork 出来的进程中使用，否则会导致死锁
logger = LoggerPool().get('point_check', file_location='logs/point_check.log')


workers = 20

@handle_step_error("操作指导步骤")  
def operate_guide_step(step_name , limit):
    global CDATA
    step_id, actual_str, judge_str, display_str, switch_str, guide_system, unit = limit
    res = {
        'actual': _eval_str(step_name, actual_str, '操作指导 actual' ),
        'aim': _eval_str(step_name, display_str, '操作指导 aim'),
        'done': True
    }

    trigger_val = _eval_str(step_name, switch_str, '操作指导 trigger_val')
    judge_val = _eval_str(step_name, judge_str,'操作指导 judge_val')
    # 触发操作指导界面
    if trigger_val == 1 or trigger_val == True:
        web_socket_data = {
            'step_id': step_id,
            'guide_system_id': guide_system
        }

        with flask_app.app_context():
            send_websocket_msg('guidance', web_socket_data, room=str(unit), broadcast=False)

        # 判断步骤是否完成
        if not (judge_val == True or judge_val == 1):
            res['done'] = False
    CDATA[step_name] = json.dumps(res)
    return json.dumps(res)

def oper_guide_task():
    global latest_ts, all_guide_steps, CDATA
    latest_ts = None
    begin = time.time()
    update_oper_step()
    latest_ts, realtime_values = update_realtime_values()
    CDATA = realtime_values.copy()
    for point_name, all_guide_step in all_guide_steps.items():
        operate_guide_step(point_name, all_guide_step)
    
    # 将实时值插入到redis中
    write_cdata_to_redis(latest_ts, glovar.CDATA)

    loguru.logger.info(f"oper guide task cost : {time.time() - begin}")

def start_point_limits_read_loop():
    def point_limits_read_loop():
        while True:
            update_point_limits()
            time.sleep(2)
    t = threading.Thread(target=point_limits_read_loop)
    t.start()

def update_oper_step():
    global all_guide_steps
    with guide_app.app_context():
        all_guide_steps = OperGuideStep.get_all_guide_steps_for_check()
def init_pool():
    global point_judge_pool, point_limits, latest_ts,realtime_values,points_status,points_warning_list
    # 为了使得运行一次后所有worker重启一次，设置为 预警进程数 20 的一倍 
    point_judge_pool = Pool(workers, context=multiprocessing.get_context('fork'), maxtasksperchild=1)


def init_point_check_task_main():
    # 初始化点名预警信息
    init_point_limit()
    # 更新实时值
    update_realtime_values()
    # 初始化 预警进程/线程池
    init_pool()
    # 启动 预警数据读取线程
    start_point_limits_read_loop()

def init_point_limit():
    global point_limits, points_status, points_warning_list
    update_point_limits()
    # 更新
    for point_limit in point_limits:
        points_status[point_limit.point_name] = point_limit.all_status
        points_warning_list[point_limit.point_name] = point_limit.current_warning_list

def update_point_limits():
    global point_limits
    with t_app.app_context():
        point_limits = PointDesc.get_all_limits()


def update_realtime_values() -> Tuple[int, Dict[str, float]]:
    global latest_ts, realtime_values
    latest_ts = int(redis.read('latest'))
    if not latest_ts:
        logger.error('初始化点检查任务错误，无法读取到 redis latest 时间戳')
        raise RuntimeError('初始化点检查任务错误，无法读取到 redis latest 时间戳')
    point_list = redis.read('all_points')
    if not point_list:
        from flask_app.common.init_origin_point_names_to_redis import init_origin_point_names
        logger.error('初始化点检查任务错误，找不到all_points, 尝试写入all points')
        init_origin_point_names()
        raise RuntimeError('初始化点检查任务错误，无法读取到 redis all_points')

    point_list = point_list.split(',')
    key_list = list(map(lambda x: '{}@{}'.format(latest_ts, x), point_list))
    for k, v in zip(point_list, redis.redis_client.mget(*key_list)):
        if v:
            realtime_values[k] = float(v)
    
    # 同时更新 glovar.CDATA  ， 是的 eval 能够正常使用
    glovar.CDATA = realtime_values
    
    return latest_ts, realtime_values



def point_judge_batch_process(start: int, end: int) -> List:
    global point_limits, latest_ts, realtime_values, points_status, points_warning_list
    n_checked_points, warning_list = point_judge_main_loop(
        realtime_values, point_limits=point_limits[start:end],points_status=points_status, points_warning_list=points_warning_list, latest_ts=latest_ts)
    return warning_list


def point_check_task():
    task_begin = time.time()
    logger.info("start", extra={
        "time": task_begin
    })
    '''
    定时任务
    判断点名的期望值（偏差上下限）、上上限、下下限以及过去一段时间的方差是否超出
    '''
    stats_map['point_judge'] = 0
    
    global latest_ts, point_limits, point_check_round, realtime_values, points_status, points_warning_list
    begin = time.time()
    update_realtime_values()
    # 遍历所有点(及其规则)
    begin = time.time()
    # 不可用redis 做 实时状态缓存，因为redis 的写入是异步的， 改为直接使用 python 字典
    # read_point_cache_info()
    total = len(point_limits)
    batch = int(total/workers)

    indices_args = list()

    if batch >= total:
        indices_args = [(0, total)]
    else:
        indices_args = list(zip(list(range(0, total+batch, batch)),
                            list(range(batch, total+batch, batch))))

    
    # results = point_judge_pool.starmap(point_judge_batch_process, indices_args)
    results = []
    futures = [point_judge_pool.apply_async(point_judge_batch_process, indice) for indice in indices_args]
    try:
        # 设置超时时间为3秒
        results = [result.get(timeout=3) for result in futures]
    except TimeoutError:
        init_pool()
        loguru.logger.error({
            "msg": "task time out",
            "trace": traceback.format_exc()
        })
        return 


    warning_list = functools.reduce(lambda a, b: a+b, results)
    point_judge_pool.apply_async(handle_all_warning_list, args=(
        warning_list, latest_ts))
    # 点名状态写入缓存，同步更新
    cache_write_point_status(warning_list)
    
    loguru.logger.info({
        "batch": batch,
        "point_judge_cost": time.time() - begin,
    })

    logger.info("end", extra={
        "time": time.time(),
        "cost": time.time() - task_begin,
    })
    point_check_round += 1


def point_check_task_in_mainloop():
    task_begin = time.time()
    logger.info("start", extra={
        "time": task_begin
    })
    '''
    定时任务
    判断点名的期望值（偏差上下限）、上上限、下下限以及过去一段时间的方差是否超出
    '''
    global latest_ts
    begin = time.time()
    update_realtime_values()


    stats_map['point_judge'] = 0
    n_checked_points, warning_list = point_judge_main_loop(
        realtime_values, point_limits=point_limits, points_status=points_status, points_warning_list=points_warning_list, latest_ts=latest_ts)
    print("stats_map['point_judge']", stats_map['point_judge'])

    handle_all_warning_list(warning_list, latest_ts)
    cache_write_point_status(warning_list)

    logger.info("end", extra={
        "time": time.time(),
        "cost": time.time() - task_begin,
    })
    print(f"end cost {currentframe().f_lineno} : {time.time() - begin}")


def point_judge_main_loop(cdata: Dict[str, float], point_limits: List[PointDesc], points_status:Dict[str, Dict[str, int]], points_warning_list:Dict[str, List], latest_ts:int) -> Tuple[int, List]:
    """point judge in a main loop 

    Args:
        pointname_limits (Dict[str, Dict]): point name to point values dict
        realtime_values (Dict[str, float]): realtime values dict
        warning_list (List): warning list to append warnings

    Returns:
        int: number of checked points
    """

    # stats_map['point_judge'] = 0
    warning_list = list()
    # point_judge_start_time = time.time()

    n_checked_points = 0
    for point_limit in point_limits:
        if point_limit is None:
            continue
        try:
            actual = cdata[point_limit.point_name]  # 取滤波后的值进行判断
        except KeyError as e:
            # logger.warning(f"该点:{point_limit.point_name}未在实时值中, 跳过点检查")
            continue

        point_begin_time = time.time()

        point_warnings = None
        try:
            point_warnings = judge_point(
                point_limit, latest_ts=latest_ts, realtime=cdata[point_limit.point_name],
                point_status= points_status.get(point_limit.point_name, None),
                point_warnings_list=points_warning_list.get(point_limit.point_name, list()))
        except:
            traceback.print_exc()
        stats_map[point_limit.point_name] = time.time() - point_begin_time
        if point_warnings is not None:
            point_warnings['unit'] = point_limit.unit
            point_warnings['point_desc'] = point_limit.describe
            warning_list.append(point_warnings)
        n_checked_points += 1

    # stats_map['point_judge'] += time.time() - point_judge_start_time
    return n_checked_points, warning_list


def point_judge_batch_thread(batch: int, thread_pool: ThreadPool, cdata: Dict[str, float], point_limits: Dict[str, Tuple]) -> Tuple[int, List]:
    """point judge in a main loop 

    Args:
        pointname_limits (Dict[str, Dict]): point name to point values dict
        realtime_values (Dict[str, float]): realtime values dict
        warning_list (List): warning list to append warnings

    Returns:
        int: number of checked points
    """

    global stats_map
    point_judge_start_time = time.time()
    n_checked_points = 0
    warning_list = list()

    def judge_point_batch(limit_batch):
        for pid, key, desc, filter_str, switch, expect, offset, upper, lower, v_duration, v_gate, unit, all_status, first_warning_list, current_warning_list in limit_batch:
            point_warnings = None
            point_begin_time = time.time()
            point_name = key

            try:
                realtime = cdata[point_name]  # 取滤波后的值进行判断
            except KeyError as e:
                logger.warning(f"该点:{point_name}未在实时值中, 跳过点检查")
                continue
            point_warnings = judge_point_old(point_name, pid, latest_ts, filter_str=filter_str, realtime=realtime, desc=desc,
                                             switch=switch, expect=expect, offset=offset, upper=upper, lower=lower,
                                             v_duration=v_duration, v_gate=v_gate, latest_ts=int(latest_ts), all_status=all_status, first_warning_list=first_warning_list, current_warning_list=current_warning_list, unit=unit)
            stats_map[point_name] = time.time() - point_begin_time
            if point_warnings is not None:
                point_warnings['unit'] = unit
                point_warnings['point_desc'] = desc
                warning_list.append(point_warnings)
            nonlocal n_checked_points
            n_checked_points += 1

    for i in range(0, len(point_limits), batch):
        thread_pool.schedule(
            judge_point_batch, args=(point_limits[i:i+batch],))
    thread_pool.close()
    thread_pool.join()
    stats_map['point_judge'] += time.time() - point_judge_start_time
    return n_checked_points, warning_list

def write_point_check_data_to_redis(latest_ts: int):
    # logger.info("cdata to redis", extra={
    #     "latest_ts": latest_ts
    # })
    result_redis.redis_client.set('warnings-latest', latest_ts)
    # 存10分钟
    result_redis.redis_client.expire(
        'warnings-latest', 500)


def write_cdata_to_redis(latest_ts: int, cdata: Dict[str, float]):
    # logger.info("cdata to redis", extra={
    #     "latest_ts": latest_ts
    # })
    CDATA_key = '{}-CDATA'.format(latest_ts)
    result_redis.redis_client.hset(CDATA_key, mapping=json.loads(
        json.dumps(cdata, cls=PowermodelJSONizer)))
    # 存60s
    result_redis.redis_client.expire(
        CDATA_key, 60)
    result_redis.redis_client.set('CDATA-latest', latest_ts)
    # 存5分钟
    result_redis.redis_client.expire(
        'CDATA-latest', 300)


def handle_all_warning_list(warning_list: List, latest_ts: int):
    """必须传入完整的warning_list，否则写入的realtime_warnings 只会是一部分

    Args:
        warning_list (List): _description_
        latest_ts (int): _description_
    """
    n_warnings, realtime_warnings = handle_warning_list(
        warning_list, latest_ts)
    with flask_app.app_context():
        redis.write("realtime_warning", json.dumps(realtime_warnings))

def cache_write_point_status(warning_list: List):
    global points_status,points_warning_list
    for point_warnings in warning_list:
        points_status[point_warnings['point_name']] = point_warnings['all_status']
        points_warning_list[point_warnings['point_name']] = point_warnings['warnings']
    
    
def handle_warning_list(warning_list: List, latest_ts: int) -> Tuple[int, List]:
    """该方法与其他方法完全解耦，只需要传入参数即可得到 对应的 realtime_warnings

    Args:
        warning_list (List): _description_
        latest_ts (int): _description_

    Returns:
        Tuple[int, List]: _description_
    """
    global flask_app

    redis_writes = list()
    realtime_warnings = list()
    tmp_new_reminders = dict()
    n_warnings = 0

    for point_warning in warning_list:
        pid = point_warning['pid']
        point_name = point_warning['point_name']
        point_desc = point_warning['point_desc']
        warnings = point_warning['warnings']
        first_warnings = point_warning['first_warning_list']  # 状态改变后的的
        unit = point_warning['unit']

        redis_writes.append(
            ('{}-{}-warnings'.format(point_name, latest_ts), json.dumps(warnings)))

        for w in warnings:
            realtime_warnings.append(w)

        for w in first_warnings:  # 只保存第一条记录
            n_warnings += 1
            new_reminder = {
                'rtype': 'point',
                'pid': pid,
                'mid': None,
                'version': None,
                'title': '{}{} 实时值报警'.format(point_name, point_desc),
                'remark': '{} {}'.format(point_name, w['msg']),
                'create_time': datetime.datetime.fromtimestamp(int(latest_ts)),
                'unit': unit,
                'first_report_flag':  w['first_report_flag'],
            }
            tmp_new_reminders[(pid, w['type'])] = new_reminder

            web_socket_data = {
                'pid': pid,
                'point_name': point_name,
                'point_desc': point_desc,
                'ts': int(latest_ts),
                'warning_type': w['type'],
                'msg': w['msg'],
                'unit': unit,
                'first_report_flag': w['first_report_flag'],
            }
            with flask_app.app_context():
                send_websocket_msg('point_check', web_socket_data,
                                   room=str(unit), broadcast=False)

    with flask_app.app_context():
        Reminder.create_reminders(tmp_new_reminders.values())
    changed_warning_list = list(
        filter(lambda x: x['status_changed'] == True, warning_list))
    with flask_app.app_context():
        PointDesc.update_point_warnings(changed_warning_list)

    with flask_app.app_context():
        with result_redis.redis_client.pipeline() as p:
            for key, value in redis_writes:
                # 预警过期时间10分钟
                p.setex(key, 600, value)
            p.execute()

        # 将实时值插入到redis中
        write_point_check_data_to_redis(latest_ts)

    return n_warnings, realtime_warnings
