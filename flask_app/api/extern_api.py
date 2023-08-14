from flask import Blueprint, g, request
from flask_app import redis
from flask_app.api import handle_error
from flask_app.common.before_request import get_request_data
from flask_app.common.extern_excel_reader import ex_reader
from flask_app.common.result import false_return, true_return

extern_blueprint = Blueprint("extern_blueprint", __name__, url_prefix='/ex')


@extern_blueprint.before_request
@handle_error
def before_request():
    if request.method == 'GET' or request.method == 'DELETE':
        g.data = request.args
        return 
    if request.content_type == 'application/json':
        g.data = request.get_json()
        return 
    g.data = request.get_json()
    
    


@extern_blueprint.route('/get_latest_values', methods=['POST'])
def get_latest_values():
    success, data = get_request_data(request, ['points'], ['points'])
    if not success:
        return false_return(data)
    
    points = data['points']
    
    latest_ts = redis.read('latest')
    if not latest_ts:
        return false_return('最新时间戳获取失败')
    
    latest_ts = int(latest_ts)
    query_keys = ['{}@{}'.format(latest_ts, point_name) for point_name in points]
    realtime_values = redis.redis_client.mget(*query_keys)

    res = dict()
    for i, point_name in enumerate(points):
        value = realtime_values[i]
        value = eval(value) if value else None
        res[point_name] = value
    
    return true_return('查询成功', res)


@extern_blueprint.route('/points', methods=['GET'])
def get_all_point_files():
    have_file_name, data = get_request_data(request, ['list_name'])
    if not have_file_name:
        return true_return('获取所有列表成功', ex_reader.get_all_file_names())
    
    file_name = data['list_name']
    success, points_list_may = ex_reader.get_point_names(file_name)
    if not success:
        return false_return(points_list_may)

    latest_ts = redis.read('latest')
    if not latest_ts:
        return false_return('最新时间戳获取失败')
    
    latest_ts = int(latest_ts)
    query_keys = ['{}@{}'.format(latest_ts, point['name']) for point in points_list_may]
    realtime_values = redis.redis_client.mget(*query_keys)

    for i, point in enumerate(points_list_may):
        value = realtime_values[i]
        if value == 'nan':
            value = None
        value = eval(value) if value else None
        point['value'] = value
    
    return true_return('实时值查询成功', points_list_may)
