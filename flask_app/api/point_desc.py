from flask import Blueprint, g, request, current_app, make_response
from flask_app.apschedule_tasks.point_check.custom_funcs import yc
from flask_app.models.origin_point_system_config import OriginPointSystemConfig
from flask_app.util.file_util import store_request_file
from flask_app.api import handle_error
from flask_app.common.before_request import get_border, get_request_data, check_page, check_unit
from flask_app.common.result import false_return, true_return
from pandas import DataFrame
from flask_app.models.system_config import SystemConfig
from flask_app.util.common.file_os import *
from flask_app.models.origin_point_dec import OriginPointDesc, write_origin_points_to_redis
from flask_app.models.point_desc import PointDesc, read_cold_from_redis
from flask_app.models.relation_map import add_all
from flask_app.util.file_util import get_file_encoding
from flask_app.util.str_util import to_bool
import traceback
import json
import io
import datetime
import chardet
import numpy as np
import multiprocessing
from flask_app import db
point_desc_blueprint = Blueprint("point_desc_blueprint", __name__, url_prefix='/point_desc')


@point_desc_blueprint.before_request
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

@point_desc_blueprint.route('/upload_file', methods=['POST'])
@handle_error
def upload_file():
    try:
        tags_desc_file = request.files['points_file']
        if tags_desc_file:
            allowed, filename, extension = allowed_upload_csv(tags_desc_file.filename)
            if not allowed:
                error_message = "文件后缀名必须是.csv"
                return false_return(error_message)
            path = store_request_file(tags_desc_file, filename, prefix="_origin_pointdesc")
            print(filename, extension)
            encoding = get_file_encoding(path)
            PointDesc.clear_table(g.unit)
            batch_create_point_desc_by_file(path, encoding)
            return true_return("文件上传成功")
        return false_return("请选择文件")
    except UnicodeDecodeError as decode_error:
        traceback.print_exc()
        return false_return('文件编码错误,无法解析,文件编码格式应为UTF-8 或 GBK 或 GB2312')
    except Exception as e:
        traceback.print_exc()
        return false_return('csv文件中需要有name和desc列, 文件编码(encoding) 需要为UTF-8 或 GBK 或 GB2312 ')


def batch_create_point_desc_by_file(file, encoding='utf-8', check=True):
    points = []
    point_name_set = set()
    data: DataFrame = pd.read_csv(file, encoding=encoding)

    point_name_list = data['点名'].tolist()
    point_desc_list = data['点描述 '].tolist()
    upper_limit_list = data['上上限H'].tolist()
    lower_limit_list = data['下下限L'].tolist()
    expect_list = data['期望值'].tolist()
    offset_list = data['D//-D'].tolist()
    switch_list = data['触发标签'].tolist()
    variance_duration_list = data['坏点时间'].tolist()
    actual_list = data['实际值'].tolist()
    # 事前校验？
    # 校验
    if check:
        result = PointDesc.check_point_name_list(point_name_list)

        def check_point_name(point_name, point_names):
            return point_name in point_names

        valid_point_name_index = []
        for index, point_name in enumerate(point_name_list):
            if check_point_name(point_name, result):
                valid_point_name_index.append(index)
    else:
        valid_point_name_index = list(range(len(point_name_list)))

    def check_nan(num):
        return num != num

    for row_index in valid_point_name_index:
        point_name = point_name_list[row_index]
        if point_name in point_name_set:
            continue
        else:
            point_name_set.add(point_name)
        point_desc = point_desc_list[row_index]
        upper_limit = upper_limit_list[row_index] if not check_nan(upper_limit_list[row_index]) else None
        lower_limit = lower_limit_list[row_index] if not check_nan(lower_limit_list[row_index]) else None
        offset = offset_list[row_index] if not check_nan(offset_list[row_index]) else None
        expect = expect_list[row_index] if not check_nan(expect_list[row_index]) else None
        switch = switch_list[row_index] if not check_nan(switch_list[row_index]) else None
        variance_duration = variance_duration_list[row_index] if not check_nan(variance_duration_list[row_index]) else None
        actual = actual_list[row_index] if not check_nan(actual_list[row_index]) else None
        variance_gate = None
        point = PointDesc(point_name=point_name, describe=point_desc, upper_limit=upper_limit, lower_limit=lower_limit,
                          expect=expect, offset=offset, switch=switch, variance_duration=variance_duration,
                          variance_gate=variance_gate, actual=actual, unit=g.unit)
        points.append(point)

    add_all(points)

@point_desc_blueprint.route('/expect_history', methods=['GET'])
@handle_error
def query_expect_history():
    from  flask_app.util.rpc.point_desc  import  point_check_get_realtime_expect_history
    have_name, data = get_request_data(request, ['name', 'history_length'])
    
    if not have_name:
        return false_return(data)
    p_name = data['name']
    history_length = int(data['history_length'])
    res = PointDesc.get_by_name(p_name, g.unit)
    if not res:
        return false_return('点预警不存在')
    history_data = point_check_get_realtime_expect_history( p_name, str(res.expect), history_length)
    return true_return("获取期望值历史数据成功",history_data)
    
    

@point_desc_blueprint.route('/refresh', methods=['GET'])
@handle_error
def refresh_point_check_variables():
    from  flask_app.util.rpc.point_desc  import  point_check_refresh_pointlimits_from_db
    status = point_check_refresh_pointlimits_from_db()
    return true_return("写入预警数据成功",status)
    


@point_desc_blueprint.route('/point', methods=['GET'])
@handle_error
def query_point():
    """
    ----------
    Args:
        pid: 点id
        name: 点名
        cid: 系统id
    ----------
    Returns:
        point: 点描述对象（单个对象或列表）
    """

    have_pid, data = get_request_data(request, ['pid'])
    if have_pid:
        pid = data['pid']
        res = PointDesc.get_by_id(pid, g.unit)
        if not res:
            return false_return('找不到指定的点预警信息')
        res = res.to_json()
        return true_return('查询成功', res)

    have_name, data = get_request_data(request, ['name'])
    if have_name:
        p_name = data['name']
        res = PointDesc.get_by_name(p_name, g.unit)
        if not res:
            return false_return('点预警不存在')
        res = res.to_json()
        return true_return('查询成功', res)

    have_cid, data = get_request_data(request, ['cid'])
    if have_cid:
        cid = data['cid']
        system = SystemConfig.get_by_id(cid, g.unit)
        if not system:
            return false_return('找不到指定系统cid-{}'.format(cid))
        res = get_children_points(system)
        return true_return("ok", res)

    # 如果id,name,cid都不存在,则获取unit中全部PointDesc
    have_page, page, size = check_page(request)
    points, total = PointDesc.get_by_page(page, size, g.unit)
    res = {
        'points': [p.to_json(full=True) for p in points],
        'total': total
    }
    return true_return('查询成功', res)



@point_desc_blueprint.route('/point_with_value', methods=['GET'])
@handle_error
def query_point_with_value():
    """
    ----------
    Args:
        pid: 点id
        name: 点名
        cid: 系统id
    ----------
    Returns:
        point: 点描述对象（单个对象或列表）
    """

    have_pid, data = get_request_data(request, ['pid'])
    if have_pid:
        pid = data['pid']
        res = PointDesc.get_by_id(pid, g.unit)
        if not res:
            return false_return('找不到指定的点预警信息')
        else:
            res = res.to_json_with_value()
            return true_return('查询成功', res)

    have_name, data = get_request_data(request, ['name'])
    if have_name:
        p_name = data['name']
        res = PointDesc.get_by_name(p_name, g.unit)
        if not res:
            return false_return('点预警不存在')
        else:
            res = res.to_json_with_value()
            return true_return('查询成功', res)

    have_cid, data = get_request_data(request, ['cid'])
    if have_cid:
        cid = data['cid']
        system = SystemConfig.get_by_id(cid, g.unit)
        if not system:
            return false_return('找不到指定系统cid-{}'.format(cid))
        res = get_children_points(system)
        return true_return("ok", res)

    # 如果id,name,cid都不存在,则获取unit中全部PointDesc
    have_page, page, size = check_page(request)
    points, total = PointDesc.get_by_page(page, size, g.unit)
    res = {
        'points': [p.to_json_with_value(full=True) for p in points],
        'total': total
    }
    return true_return('查询成功', res)


@point_desc_blueprint.route('/point_with_value/<point_name>', methods=['GET'])
@handle_error
def get_point_val_by_name(point_name):
    if not point_name:
        return false_return("请传入正确的点名参数")
    res = PointDesc.get_by_name(point_name, g.unit)
    if not res:
        return false_return('点预警不存在')
    res = res.to_json_with_value()
    return true_return('查询成功', res)


@point_desc_blueprint.route('/point_names', methods=['POST'])
def get_multi_points():
    '''
    通过点英文名一次获取多个点预警的信息
    '''
    success, data = get_request_data(request, ['names'], ['names'])
    if not success:
        return false_return(data)

    point_names = data['names']
    points = PointDesc.get_points_by_names(point_names)

    return true_return('查询成功', [p.to_json() for p in points])


@point_desc_blueprint.route('/multi_search_with_value', methods=['GET'])
def multi_search_with_value():
    """
    多条件查询点预警信息
    ----------
    Args:
        point_name: 点名
        point_desc: 点名描述
        system: 系统名
        system_alias: 系统别名
    ----------
    Returns:
        points: 原始点对象（列表）
    """
    _, page, size = check_page(request)
    # have_page, left, right = get_border(request)

    point_name = g.data.get('point_name')
    point_desc = g.data.get('point_desc')
    system = g.data.get('system')
    system_alias = g.data.get('system_alias')

    selected_points, total = PointDesc.search_all(point_name, point_desc, system, system_alias, g.unit, page, size)

    res = {
        'points': [p.to_json_with_value() for p in selected_points],
        'total': total
    }

    return true_return('筛选成功', res)

@point_desc_blueprint.route('/multi_search', methods=['GET'])
def multi_search():
    """
    多条件查询点预警信息
    ----------
    Args:
        point_name: 点名
        point_desc: 点名描述
        system: 系统名
        system_alias: 系统别名
    ----------
    Returns:
        points: 原始点对象（列表）
    """
    _, page, size = check_page(request)
    # have_page, left, right = get_border(request)

    point_name = g.data.get('point_name')
    point_desc = g.data.get('point_desc')
    system = g.data.get('system')
    system_alias = g.data.get('system_alias')

    selected_points, total = PointDesc.search_all(point_name, point_desc, system, system_alias, g.unit, page, size)

    res = {
        'points': [p.to_json() for p in selected_points],
        'total': total
    }

    return true_return('筛选成功', res)


@point_desc_blueprint.route('point', methods=['POST'])
def create_point():
    """
    创建点预警信息
    """
    success, data = get_request_data(request, ['name', 'desc', 'upper_limit', 'lower_limit'], list_fields=['sub_system'])
    if not success:
        return false_return(data)

    # 创建点名
    point_name = data['name']
    existed_point = PointDesc.get_by_name(point_name, g.unit)
    if existed_point:
        return false_return('点名重复')

    point_desc = data['desc']
    actual = data.get('actual')
    expect = data.get('expect')
    offset = data.get('offset')
    upper_limit = data['upper_limit']
    lower_limit = data['lower_limit']
    switch = data.get('trigger_tag')
    v_duration = data.get('variance_duration')
    v_gate = data.get('variance_gate')
    v_gate = float(v_gate) if v_gate else None
    show_upper = data.get('show_upper')
    show_upper = float(show_upper) if show_upper else None
    show_lower = data.get('show_lower')
    show_lower = float(show_lower) if show_lower else None
    order = data.get('order')
    sys_list = data.get('sub_system')

    sys_name_list = list()
    # key => name, value => cid  注意：应确保每个系统name对应唯一 一个cid，才能根据该方法进行索引
    sys_total = SystemConfig.get_all_id_and_names_in_unit(g.unit)
    for row in sys_total:
        sys_name_list.append((row.name, int(row.cid)))
    sys_name_list = dict(sys_name_list)

    # 
    if expect is None or expect == '':
        try:
            yc(point_name)
            expect = f"yc('{point_name}')"
        except KeyError: 
            expect = f"CDATA['{point_name}']"
            
    
    origin_point = OriginPointDesc.get_by_name(point_name, int(g.unit))
    # print(origin_point)
    if origin_point is None:
        origin_point = OriginPointDesc.create_origin_point_desc(tag_name=point_name, describe=point_desc, unit=int(g.unit))

    # 前面已经判断过是否重复了
    # point = PointDesc.get_by_name(point_name, int(g.unit))
    # if point:
    #     return false_return("点名重复")
    db_success, db_res = PointDesc.create_point(point_name=point_name, describe=point_desc, expect=expect, offset=offset, upper_limit=upper_limit,
                                                lower_limit=lower_limit, switch=switch, v_duration=v_duration, v_gate=v_gate, show_upper=show_upper,
                                                show_lower=show_lower, actual=actual, order=order, unit=int(g.unit))
    if not db_success:
        return false_return(db_res)
    # 插入系统关系
    confs = []
    for sys in sys_list:
        if sys in sys_name_list.keys():
            confs.append(OriginPointSystemConfig(origin_point=point_name, system_config=sys_name_list.get(sys)).to_dict())
    if len(confs):
        OriginPointSystemConfig.upsert_all(records=confs)
    return true_return('创建成功', db_res.to_json())


@point_desc_blueprint.route('point', methods=['DELETE'])
@handle_error
def delete_point():
    """删除点预警
    """
    success, data = get_request_data(request, ['pid'])
    if not success:
        return false_return(data)

    pid = data['pid']
    point = PointDesc.get_by_id(pid, g.unit)

    if not point:
        return false_return('找不到指定点')

    PointDesc.delete_point(pid)
    return true_return(msg='删除成功')


@point_desc_blueprint.route('point', methods=['PUT'])
@handle_error
def update_point():
    """更新点预警规则
    """
    success, data = get_request_data(request, ['pid'])
    if not success:
        return false_return(data)

    pid = data['pid']
    target_point = PointDesc.get_by_id(pid, g.unit)
    if not target_point:
        return false_return('找不到指定点')

    updata_data = g.data
    if 'desc' in updata_data:
        updata_data['describe'] = updata_data['desc']
        del updata_data['desc']
    if 'trigger_tag' in updata_data:
        updata_data['switch'] = updata_data['trigger_tag']
        del updata_data['trigger_tag']
    del updata_data['pid']

    error_msg = None
    if "systems" in updata_data:
        error_msg = OriginPointDesc.change_systems(target_point.point_name)

    # 更细PointDesc时， 不更新point_name！！
    result, msg = PointDesc.update_point(pid, updata_data, g.unit)
    if result and error_msg is None:
        return true_return('修改成功')
    else:
        return false_return(f"{msg} {error_msg}")


@point_desc_blueprint.route('point_by_name', methods=['PUT'])
@handle_error
def update_point_by_name():
    """更新点预警规则
    """
    success, data = get_request_data(request, ['point_name'])
    if not success:
        return false_return(data)

    point_name = data['point_name']
    target_point = PointDesc.get_by_name(point_name, g.unit)
    if not target_point:
        return false_return('找不到指定点')

    updata_data = g.data
    if 'desc' in updata_data:
        updata_data['describe'] = updata_data['desc']
        del updata_data['desc']
    if 'trigger_tag' in updata_data:
        updata_data['switch'] = updata_data['trigger_tag']
        del updata_data['trigger_tag']
    del updata_data['point_name']

    error_msg = None
    if "systems" in updata_data:
        error_msg = OriginPointDesc.change_systems(target_point.point_name)

    # 更细PointDesc时， 不更新point_name！！
    result, msg = PointDesc.update_point_by_name(point_name, updata_data, g.unit)
    if result and error_msg is None:
        return true_return('修改成功')
    else:
        return false_return(f"{msg} {error_msg}")

def get_children_points(system):
    res = []
    if system and not system.children:
        point_names = [origin_point['point_name'] for origin_point in system.to_json()['origin_points']]
        points = PointDesc.get_points_by_names(point_names)
        res = [point.to_json() for point in points]
    else:
        for child in system.children.split(','):
            sub_system = SystemConfig.get_by_name(child, g.unit)
            res.extend(get_children_points(sub_system))
    return res


@point_desc_blueprint.route('/eval', methods=['POST'])
@handle_error
def eval_code():
    from  flask_app.util.rpc.point_desc  import  point_check_eval
    success, data = get_request_data(request, ['code_str'])
    if not success:
        return false_return(data)
    
    res = point_check_eval(data['code_str'])
    return true_return(data=res, msg='eval成功执行')

@point_desc_blueprint.route('/variance', methods=['GET'])
@handle_error
def get_variance():
    from  flask_app.util.rpc.point_desc  import  point_check_get_variance
    success, data = get_request_data(request, ['point_name', 'duration'])
    if not success:
        return false_return(data)  
    res = point_check_get_variance(str(data['point_name']), int(data['duration']))
    return true_return(data=float(res), msg='方差计算成功执行')



@point_desc_blueprint.route('/offset_eval', methods=['POST'])
@handle_error
def offset_eval_code():
    from  flask_app.util.rpc.point_desc  import point_check_offset_eval
    success, data = get_request_data(request, ['code_str'])
    if not success:
        return false_return(data)
    
    res = point_check_offset_eval(data['code_str'])
    return true_return(data=res, msg='偏差值计算成功执行')

@point_desc_blueprint.route('/actual_eval', methods=['POST'])
@handle_error
def actual_eval_code():
    from  flask_app.util.rpc.point_desc  import  point_check_filter_eval
    success, data = get_request_data(request, ['point_name', 'code_str'])
    if not success:
        return false_return(data)
    
    res = point_check_filter_eval(data['point_name'],data['code_str'])
    return true_return(data=res, msg='滤波计算成功执行')


@point_desc_blueprint.route('/status', methods=['PUT'])
@handle_error
def update_point_status():
    success, data = get_request_data(request, ['point_name', 'all_status'])
    if not success:
        return false_return(data)
    
    point_name = data['point_name']
    all_status = data['all_status']
    if PointDesc.update_all_status(point_name, all_status):
        return true_return('更新成功')
    else:
        return false_return('更新状态失败')


@point_desc_blueprint.route('/logs', methods=['GET'])
@handle_error
def point_desc_logs():
    success, data = get_request_data(request, ['point_name', 'type'])
    if not success:
        return false_return(data)
    point_name = data['point_name']
    point_path = f'/workspace/power_model_system/logs/{point_name}/run.log'
    
    
    log_path = point_path # os.path.join(model_path, 'logs', '{}{}.log'.format(stage, type_str))
    if not os.path.exists(log_path):
        return false_return('找不到日志文件 {}'.format(log_path))

    have_page, left, right = get_border(request)
    if have_page:
        with open(log_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        res = {
            'total': len(all_lines),
            'log_lines': all_lines[left: right]
        }
        return true_return('分页查询成功', res)

    n_tail_lines = int(data.get('num_lines', 50))
    log_lines = tail_file(log_path, n_tail_lines)

    return true_return('查询成功', log_lines)

#导入模板批量创建点预警
@point_desc_blueprint.route('batch_points', methods=['POST'])
def create_points_api():
    """
    批量创建点预警信息
    """
    try:
        tags_file = request.files['point_desc_file']
        if tags_file:
            allowed, filename, extension = allowed_upload_csv(tags_file.filename)
            if not allowed:
                error_message = "文件后缀名必须是.csv"
                return false_return(msg=error_message)
            file = chardet.detect(tags_file.read())
            format = file['encoding']
            tags_file.seek(0)
            data = pd.read_csv(tags_file, encoding=format)
            data = data.replace(np.nan, '', regex=True)
            point_name_list = data['name'].tolist()
            point_desc_list = data['desc'].tolist()
            sys_list = data['systems'].tolist()
            actual_list = data['actual'].tolist()
            expect_list = data['expect'].tolist()
            offset_list = data['offset'].tolist()
            upper_limit_list = data['upper_limit'].tolist()
            lower_limit_list = data['lower_limit'].tolist()
            switch_list = data['trigger_tag'].tolist()
            v_duration_list = data['variance_duration'].tolist()
            v_gate_list = data['variance_gate'].tolist()
            show_upper_list = data['show_upper'].tolist()
            show_lower_list = data['show_lower'].tolist()
            # ordr_list = data['order'].tolist()
            ctx = multiprocessing.get_context('spawn')
            sys_name_list = []
            # key => name, value => cid  注意：应确保每个系统name对应唯一 一个cid，才能根据该方法进行索引
            sys_total = SystemConfig.get_all_id_and_names_in_unit(g.unit)
            for row in sys_total:
                sys_name_list.append((row.name, row.cid))
            sys_name_list = dict(sys_name_list)
            # create_points(point_name_list, point_desc_list,sys_name_list,sys_list, actual_list, expect_list, offset_list, upper_limit_list, lower_limit_list,
            #       switch_list, v_duration_list, v_gate_list, show_upper_list,
            #       show_lower_list, g.unit)
            db.get_engine(app=current_app).dispose()
            ctx = multiprocessing.get_context('spawn')
            p = ctx.Process(target=create_points, args=(point_name_list, point_desc_list,sys_name_list,sys_list, actual_list, expect_list, offset_list, upper_limit_list, lower_limit_list,
                  switch_list, v_duration_list, v_gate_list, show_upper_list,
                  show_lower_list, g.unit))
            p.start()
            return true_return(msg="正在批量创建点预警")
        else:
            return false_return(msg='上传的点预警文件不能为空')
    except UnicodeDecodeError as e:
        traceback.print_exc()
        return false_return(msg='编码格式错误')
    except Exception as e:
        traceback.print_exc()
        return false_return(msg='csv文件中缺少相应列')
    
def create_points(point_name_list, point_desc_list,sys_name_mapper,sys_list_str, actual_list, expect_list, offset_list, upper_limit_list, lower_limit_list, switch_list, v_duration_list, v_gate_list, show_upper_list,
                  show_lower_list, unit):
    # 批量创建点名
    for i in range(len(point_name_list)):
        try:
            point_name = point_name_list[i]
            # existed_point = PointDesc.get_by_name(point_name, unit)
            # if existed_point:
            #     print(f"点名存在在预警中，覆盖:{point_name}")
            #     continue
            point_desc = point_desc_list[i]
            sys_list = str(sys_list_str[i]).strip().split(' ')
            actual = actual_list[i]
            expect = expect_list[i]
            offset = offset_list[i]
            upper_limit = upper_limit_list[i]
            lower_limit = lower_limit_list[i]
            switch = switch_list[i]
            v_duration = v_duration_list[i]
            v_gate = v_gate_list[i]
            v_gate = float(v_gate) if v_gate else None
            show_upper = show_upper_list[i]
            show_upper = float(show_upper) if show_upper else None
            show_lower = show_lower_list[i]
            show_lower = float(show_lower) if show_lower else None
            # order = ordr_list[i]
            if expect is None or expect == '':
                try:
                    yc(point_name)
                    expect = f"yc('{point_name}')"
                except KeyError: 
                    expect = f"CDATA['{point_name}']"
            origin_point = OriginPointDesc.get_by_name(point_name, int(unit))
            # print(origin_point)
            if origin_point is None:
                origin_point = OriginPointDesc.create_origin_point_desc(tag_name=point_name, describe=point_desc, unit=int(unit))
            
            point = PointDesc.get_by_name(point_name, int(unit))
            if point:
                print(f"点名存在在预警中，覆盖:{point_name}")
                PointDesc.update_point_by_name(point_name=str(point_name), data={
                    'actual':str(actual),
                    'expect':expect,
                    'offset':offset,
                    'upper_limit':upper_limit,
                    'lower_limit':lower_limit,
                    'switch':switch,
                    'variance_duration':v_duration,
                    'variance_gate':v_gate,
                    'show_upper':show_upper,
                    'show_lower':show_lower}
                                        , unit=int(unit))
            else:
                db_success, db_res = PointDesc.create_point(point_name=point_name, describe=point_desc, expect=expect, offset=offset, upper_limit=upper_limit,
                                            lower_limit=lower_limit, switch=switch, v_duration=v_duration, v_gate=v_gate, show_upper=show_upper,
                                            show_lower=show_lower, actual=actual, unit=int(unit))

            # 插入系统关系
            sys_list_filter, confs = [], []
            for sys in sys_list:
                if sys in sys_name_mapper.keys():
                    sys_list_filter.append(sys_name_mapper.get(sys))
            
            for cid in sys_list_filter:
                confs.append(OriginPointSystemConfig(origin_point=point_name, system_config=cid).to_dict())
            if len(confs):
                OriginPointSystemConfig.upsert_all(records=confs)
                continue
            
        except Exception:
            print(traceback.format_exc())
            continue
    write_origin_points_to_redis(origin_point=True, inter_variable=False)


@point_desc_blueprint.route('/batch_points', methods=['DELETE'])
@handle_error
def delete_points_api():
    PointDesc.delete_all()
    return true_return("全部预警点删除成功")


@point_desc_blueprint.route('/download', methods=['GET'])
@handle_error
def download_file():
    point_name = g.data.get("point_name", None)
    point_desc = g.data.get("describe", None)
    sys_name = g.data.get("name", None)
    sys_alias = g.data.get("alias", None)
    all_unit = g.data.get("all_unit", False)
    
    all_unit = to_bool(all_unit)
    
    return_points, size = PointDesc.search_all_no_page(point_name, point_desc, sys_name, 
                                                       sys_alias, g.unit, all_unit=all_unit)
    
    if size:
        out = io.BytesIO()
        filename = str(datetime.date.today()) + 'point_desc' + '.csv'
        return_points = format_data(return_points)
        return_points = DataFrame(return_points)
        return_points.to_csv(out, index=False)
        
        out.seek(0)
        # return send_file(out, mimetype='text/csv', as_attachment=True, attachment_filename=filename)
        
        response = make_response(out.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Content-Disposition'] = 'attachment; filename=' + filename
        return response
    else:
        return false_return("no data", None)


def format_data(points):
    return_points = {
        "name": [],
        "desc": [],
        "actual": [],
        "expect": [],
        "offset": [],
        "upper_limit": [],
        "lower_limit": [],
        "trigger_tag": [],
        "variance_duration": [],
        "variance_gate": [],
        "show_upper": [],
        "show_lower": [],
        "systems": []
    }
    for point in points:
        return_points["name"].append(point.point_name)
        return_points["desc"].append(point.describe)
        return_points["actual"].append(point.actual)
        return_points["expect"].append(point.expect)
        return_points["offset"].append(point.offset)
        return_points["upper_limit"].append(point.upper_limit)
        return_points["lower_limit"].append(point.lower_limit)
        return_points["trigger_tag"].append(point.switch)
        return_points["variance_duration"].append(point.variance_duration)
        return_points["variance_gate"].append(point.variance_gate)
        return_points["show_upper"].append(point.show_upper)
        return_points["show_lower"].append(point.show_lower)
        return_points["systems"].append(point.systems)
    return return_points


@point_desc_blueprint.route('/init_page', methods=['GET'])
@handle_error
def get_init_data():
    success, data = get_request_data(request, ['init_data_type'])
    if not success:
        return false_return("no \'init_data_type\'")
    # 具体的dtype类型位于point_check当中的write_cold_obj_redis : point_create_init / realtime_init
    dtype = data.get('init_data_type')
    success, init_data = read_cold_from_redis(dtype, g.unit)
    if not success:
        return false_return("没有读取到数据，请检查参数")
    return true_return('成功获取初始数据', init_data)
