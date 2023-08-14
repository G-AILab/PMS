import json
import os
from time import time
import traceback
from flask import Blueprint,g, request
from flask_app import redis
from flask_app import flask_app
from flask_app.api.system_config import get_score_of_all_system
from flask_app.common.before_request import check_unit, get_border, get_request_data
from flask_app.common.result import false_return, true_return
from flask_app.config.default import Config
from flask_app.models.pageconf import Pageconf
from flask_app.util.common.file_os import allowed_upload
from flask_app.api import handle_error
from  flask_app.util.rpc.point_desc  import  point_check_get_CDATA_value,point_check_get_MID_value,point_check_eval,point_check_filter_eval,point_check_offset_eval
from flask_app.apschedule_tasks.point_check.custom_funcs import get_his
from flask_app import _get_config
import redis
pageconf_blueprint = Blueprint(
    "pageconf_blueprint", __name__, url_prefix='/pageconf')


@pageconf_blueprint.before_request
@handle_error
def before_request():
    success, msg = check_unit()
    if not success:
        return false_return(msg)
    if request.method == 'GET' or request.method == 'DELETE':
        g.data = request.args
        return 
    if request.content_type == 'application/json':
        g.data = request.get_json()


@pageconf_blueprint.route('', methods=['POST'])
@handle_error
def create_pageconf():
    success, data = get_request_data(request, ['page', 'component', 'value'])
    if not success:
        return false_return(data)
    # success, msg = check_unit()
    # if not success:
    #     return false_return(msg)

    page = data['page']
    component = data['component']
    value = data['value']
    pageconf = Pageconf.create(page, component, value, g.unit)
    return true_return("创建成功", pageconf.to_json())


@pageconf_blueprint.route('', methods=['PUT'])
@handle_error
def update_pageconf():
    success, data = get_request_data(request, ['page', 'component', 'value'])
    if not success:
        return false_return(data)
    # success, msg = check_unit()
    # if not success:
    #     return false_return(msg)

    page = data['page']
    component = data['component']
    value = data['value']
    pageconf =  Pageconf.get_by_page_component(page, component, g.unit)
    if pageconf is None:
        Pageconf.create(page, component, value, g.unit)
    Pageconf.update(page, component,g.unit, {'page':page, 'component':component, 'value':value, 'unit': g.unit})
    return true_return("修改成功")


@pageconf_blueprint.route('/value', methods=['GET'])
@handle_error
def get_page_value():
    success, data = get_request_data(request, ['page'])
    if not success:
        return false_return(data)
    
    # success, msg = check_unit()
    # if not success:
    #     return false_return(msg)
    
    res = dict()
    page = data['page']
    pageconfs, total = Pageconf.get_by_page(page, g.unit)
    for pageconf in pageconfs:
        pageconf_dict = pageconf.to_json()
        component = get_component_value(pageconf_dict['value'],g.unit)
        res[pageconf_dict['component']] = component
    return true_return('获取成功', res)

    
def get_component_value(component, unit):
    point_list = component.get('point_list', None)
    new_point_list = list()
    # latest_ts = redis.read('latest')
    # if point_list is not None:
    #     for point in point_list:
    #         # try:
    #         #     # point_value = point_check_get_CDATA_value(point["point_name"])
    #         #     # if point_value is None:
    #         #     #     point_value = point_check_get_MID_value(point["point_name"])
    #         # except:
    #         #     point_value = None
    #         point_value = redis.read(f'{latest_ts}@{point["point_name"]}')
    #         point.update({'point_value':point_value})
            
            
    #         # if point['point_type'] == 0: # 原始点
                
    #         # else: # 中间变量
    #         #     point_value = point_check_get_MID_value(point["point_name"])
    #         #     point.update({'point_value':float(point_value)})
            
    #         new_point_list.append(point)
    #     component.update({'point_list':point_list})
    # 系统评分
    system_list = component.get('system_list', None)
    new_system_list = list()
    if system_list is not None:
        for system in system_list:
            score = get_score_of_all_system(system['id'], unit)
            system.update({'score': score})
            new_system_list.append(system)
        component.update({'system_list':system_list})
    
    # 历史数据
    # point_history = component.get('point_history', None)
    # if point_history is not None:
    #     if isinstance(point_history, dict):
    #         point_name = point_history['point_name']
    #         time = point_history['time']
    #         history = get_his(point_name, time)
    #         component.update({'history':history})
    #     elif isinstance(point_history, list):
    #         new_point_history = list()
    #         for _point_history in point_history:
    #             point_name = _point_history['point_name']
    #             time = _point_history['time']
    #             history = get_his(point_name, time)
    #             _point_history.update({'history':history})
    #             new_point_history.append(_point_history)
    #         component.update({'point_history':new_point_history})



    return component
    
    
    
  

@pageconf_blueprint.route('', methods=['GET'])
@handle_error
def get_all():
    success, data = get_request_data(request, [])
    if not success:
        return false_return(data)
    # success, msg = check_unit()
    # if not success:
    #     return false_return(msg)

    page = data.get('page', None)
    component = data.get('component', None)

    if page and component:
        pageconf = Pageconf.get_by_page_component(page, component, g.unit)
        return true_return("查询成功", pageconf.to_json())
    
    elif page:
        pageconfs,total = Pageconf.get_by_page(page, unit=g.unit)
    else:
        pageconfs,total = Pageconf.get_all()
    res = {
        'pageconfs':[p.to_json() for p in pageconfs],
        'total':total
    }
    return true_return("查询成功", res)


@pageconf_blueprint.route('/value', methods=['DELETE'])
@handle_error
def delete_component():
    """
    从页面组件中删除元素

    Args:
        for example: dtype: str = 'point_list' or dtype = 'point_history' or dtype = 'system_list'
        当dtype选择point_list或者point_history时, 以point_name为删除参考
        当dtype选择system_list时, 以为system_id删除参考
    """
    point_name = g.data.get('point_name', None)
    sys_id = g.data.get('system_id', None)
    success, data = get_request_data(request, ['page', 'component', 'dtype'])
    if not success:
        return false_return("缺少必要参数")
    
    try:
        page = data['page']
        component = data['component']
        dtype = data['dtype']
        has_del, msg = Pageconf.delete_point_system(page, component, g.unit, dtype, point_name, sys_id)
        if has_del:
            return true_return(msg)
        else:
            return false_return(msg)
    except Exception as e:
        traceback.print_exc()
        return false_return(f"错误: {str(e)}")


@pageconf_blueprint.route('/value', methods=['POST'])
@handle_error
def add_value_element():
    """
    向相应的页面组件中添加元素

    Args:
        records应做成 json字符串 形式传入, adtype指明需要向哪种组件当中添加元素
        for example: records: list = [{"point_name": "a", "point_describe": "xxx"}, {...}]
        for example: adtype: str = 'point_list' or adtype = 'point_history' or adtype = 'system_list'
    """
    success, data = get_request_data(request, ['page', 'component', 'adtype', 'records'],list_fields=['records'])
    if not success:
        return false_return(request.args)
    
    # db_data = {
    #     'point_name': data['point_name'],
    #     'point_describe': data['point_describe']
    # }
    # pname = data['point_name']
    # pdesc = data['point_describe']
    try:
        page = data['page']
        component = data['component']
        adtype = data['adtype']
        records = list(data['records'])
        
        dep_records = []
        # 去重
        if adtype == 'point_list' or adtype == 'point_history':
            # records 去重
            
            pageconf = Pageconf.get_by_page_component(page, component, g.unit)
            existed_records:list = pageconf.value[adtype]
            existed_points = set(list(map( lambda record: record['point_name'],existed_records)))
            
            add_set = set()
            for record in records:
                if record['point_name'] not in add_set and record['point_name'] not in existed_points:
                    add_set.add(record['point_name'])
                    dep_records.append(record)
        records = dep_records

        
        has_add, msg = Pageconf.add_element(page, component, g.unit, records, adtype)
        if has_add:
            return true_return(msg)
        else:
            return false_return(msg)
    except Exception as e:
        traceback.print_exc()
        return false_return(f"错误: {str(e)}")


# 任务：监控台多点实时数据接口
# 需求：get方法，根据多个点名获取其历史数据
@pageconf_blueprint.route('/multivalue', methods=['GET'])
@handle_error
def get_multipoint_data():
    
    success, data = get_request_data(request, ['point_names', 'history_length'])
    if not success:
        return false_return(request.args)
    
    ip = _get_config.REDIS_HOST
    port = _get_config.REDIS_PORT
    r = redis.Redis(host=ip, port=port, db=0, decode_responses=True)
    
    point_names = data.get('point_names').split(',')
    # 去除点名两边可能存在的空格
    point_names = [point_name.strip() for point_name in point_names]
    
    # 历史时间长度固定为600
    history_length = int(data.get('history_length'))
    ts = int(r.get('latest'))
    start_time = ts - history_length
    ts_history = [i for i in range(start_time+1, ts+1)]
    
    res = {}
    with r.pipeline() as p:
        for point_name in point_names:
            keys = ['{}@{}'.format(i, point_name) for i in ts_history]
            p.mget(*keys)
            history_data = p.execute()[0]
            # 将str转换为float
            for i in range(0, len(history_data)):
                try:
                    history_data[i] = float(history_data[i])
                except:
                    history_data[i] = None
            res_point = {
                'ts_history' : ts_history,
                'data' : history_data
            }
            res[point_name] = res_point
    return true_return("查询成功", res)
