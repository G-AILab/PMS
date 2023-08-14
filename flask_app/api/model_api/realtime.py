import json
import time

from flask import g, request
from flask_app import redis, result_redis
from flask_app.common.before_request import (check_page, get_border,
                                             get_request_data)
from flask_app.common.result import false_return, true_return
from flask_app.models.dataset import Dataset
from flask_app.models.model import Model
from flask_app.models.point_desc import PointDesc

from . import model_blueprint


attribute_keys = []


@model_blueprint.route('/attributes', methods=['GET'])
def get_all_attributes():
    '''
    自动补全点标签名
    例, 查询'N3'返回['N3DCS.3TEMS106AI', 'N3DCS...', ...]
    '''
    global attribute_keys
    success, data = get_request_data(request, ['name'])
    if not success:
        return false_return(data)
    name = data['name']
    attribute_keys = get_attributes()
    result = [item for item in attribute_keys if name in item]
    return true_return('匹配成功', result)


def get_attributes():
    # r = redis.get_max_ts()
    all_points = redis.read('all_points')
    if not all_points:
        return None
    # data = redis.hgetall(name=r)
    all_points = all_points.split(',')
    # all_points = json.loads(all_points)
    return all_points
    # return {p: 0 for p in all_points}


@model_blueprint.route('/monitor', methods=['GET'])
def get_recent_data():
    ts = g.data.get('time', 1)
    ts = int(ts)
    data = dict()
    realtime_data = redis.get_all_ts()
    realtime_data = realtime_data[-ts:]
    for item in realtime_data:
        item_data = redis.hgetall(name=item)
        data[item] = item_data
    return true_return(data=data)


@model_blueprint.route('/recent_predict_results', methods=['GET'])
def get_recent_predict_results():
    '''
    此接口应被get_predict_results()替代，不再维护
    2022.2.28
    '''
    yname = g.data.get('yname')
    duration = int(g.data.get('duration', 1))
    ts = int(time.time())
    info = {}
    info['horizon'] = 18
    info['data'] = []
    for i in range(duration):
        key = yname + '-' + str(ts-i)
        result = result_redis.read(key)
        info['data'].append(result)
    return true_return(data=info)


@model_blueprint.route('/predict_results', methods=['GET'])
def get_predict_results():
    success, data = get_request_data(request, ['yname', 'category'])
    if not success:
        return false_return(data)

    yname = data['yname']
    category = data['category']
    # print(category)
    duration = int(data.get('duration', 1))
    interval = int(data.get('interval', 1))
    ts = redis.read('latest')
    if not ts:
        return false_return('实时数据读取失败')
    ts = int(ts)
    # ts = int(time.time())

    show_up_limit, show_low_limit = None, None
    ypoint = PointDesc.get_by_name(yname, g.unit)
    if ypoint:
        show_up_limit = ypoint.show_upper
        show_low_limit = ypoint.show_lower

    info = {'horizon': 0, 'data': [], 'up_limit': show_up_limit, 'low_limit': show_low_limit}

    model = Model.get_by_yname_and_category(yname=yname, category=category, unit=g.unit)
    if model is None:
        keys = ['{}@{}'.format(ts - t, yname) for t in range(0, duration, interval)]
        # print(keys)
        realtime_values = redis.redis_client.mget(*keys)
        # print(realtime_values)
        for i, t in enumerate(range(0, duration, interval)):
            # ts = ts - 1
            tt = ts - t
            result = {
                "current": 0.0,
                "pred": None,
                "ts": int(tt),
                "yname": yname
            }
            current_value = realtime_values[i]
            # current_value = redis.hget(name=str(tt), key=yname)
            result['current'] = float(current_value) if current_value else current_value
            info['data'].append(result)
        return true_return("找不到运行中模型，只返回实时值", data=info)

    dataset = Dataset.get_by_id(model.dataset)
    params = json.loads(model.general)
    try:
        if category == 'prediction':
            info['horizon'] = params['horizon'] * dataset.sample_step
        else:
            info['horizon'] = 0
    except:
        info['horizon'] = 0
    values = []
    # yname = yname + '-' + category
    keys = ['{}-{}-{}'.format(yname, category, ts - t) for t in range(0, duration, interval)]
    # print(keys)
    model_res_values = result_redis.redis_client.mget(*keys)
    # print(model_res_values)

    for i, t in enumerate(range(0, duration, interval)):
        # ts = ts - 1
        tt = ts - t
        # key = '{}-{}-{}'.format(yname, category, tt)
        # key = yname + '-' + str(tt)
        # result = result_redis.read(key)
        result = model_res_values[i]
        if result is not None:
            values.append(json.loads(result))
    info['data'] = values
    return true_return(data=info)


# def get_model_cache(yname, category):
#     # 需要horizon再加
#     print('not cached')
#     key = str(yname) + '-' + category
#     if model_horizon_cache.get(key) is None:
#         model = Model.get_by_yname_and_category(yname=yname, category=category)
#         params = json.loads(model.general)
#         if params.get('horizon') is None:
#             params['horizon'] = 0
#         model_horizon_cache[key] = params['horizon']
#         print('not cached')
#     return model_horizon_cache.get(key)


@model_blueprint.route('/result_list', methods=['POST'])
def get_models_result():
    success, data = get_request_data(request, ['yname', 'category'], ['yname', 'category'])
    if not success:
        return false_return(data)

    ynames = data['yname']
    categories = data['category']
    if len(ynames) != len(categories):
        return false_return('点名与类别列表长度不一致')

    # ts = str(int(time.time()) - 1)
    ts = redis.read('latest')
    final_results = list()

    realtime_data_keys = list()
    realtime_warning_keys = list()
    model_res_keys = list()
    for yname, category in zip(ynames, categories):
        if category == 'detection':
            key = 'Subsystem{}-{}'.format(yname, ts)
            realtime_warning_keys.append('-')
        else:
            key = '{}-{}-{}'.format(yname, category, ts)
            realtime_warning_keys.append('{}-{}-warnings'.format(yname, ts))
        model_res_keys.append(key)
    
    if len(model_res_keys) == 0:
        return true_return('', final_results)

    model_res_values = result_redis.redis_client.mget(*model_res_keys)
    realtime_warning_values = result_redis.redis_client.mget(*realtime_warning_keys)

    for j, res in enumerate(model_res_values):
        if not res:
            realtime_data_keys.append('{}@{}'.format(ts, ynames[j]))

    realtime_data_values = list()
    if len(realtime_data_keys) > 0:
        realtime_data_values = redis.redis_client.mget(*realtime_data_keys)

    realtime_map = {k.split('@')[1]: v for k, v in zip(realtime_data_keys, realtime_data_values)}
    
    for k, res in enumerate(model_res_values):
        if res:
            final_results.append(json.loads(res))
        elif categories[k] == 'detection':
            final_results.append(None)
        else:
            warnings = json.loads(realtime_warning_values[k]) if realtime_warning_values[k] else None
            current = float(realtime_map[ynames[k]]) if ynames[k] in realtime_map and realtime_map[ynames[k]] else None
            res_tmp = {
                "current": current,
                "pred": None,
                "ts": int(ts),
                "yname": ynames[k],
                "warnings": warnings
            }
            final_results.append(res_tmp)

    return true_return('', final_results)


@model_blueprint.route('/detection_results', methods=['GET'])
def get_detection_results():
    sub_system = g.data.get('sub_system')
    duration = int(g.data.get('duration', 1))
    ts = int(time.time())
    data = []
    for i in range(duration):
        ts = ts - 1
        key = 'Subsystem' + str(sub_system) + '-' + str(ts)
        result = result_redis.read(key)
        if result is not None:
            data.append(json.loads(result))
    return true_return(data=data)
