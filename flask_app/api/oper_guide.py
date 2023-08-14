import datetime
import io
import json
import traceback
import pandas as pd
from flask import Blueprint, g, make_response, request
from flask_app import redis, result_redis, _get_config
from flask_app.api import handle_error
from flask_app.common.before_request import get_request_data, check_page, check_unit
from flask_app.common.result import false_return, true_return
from flask_app.models.oper_guide_step import OperGuideStep
from flask_app.models.oper_guide_system import OperGuideSystem
from flask_app.util.common.file_os import allowed_upload_csv
from flask_app.util.str_util import to_bool
from flask_app.util.token_auth import auth
from flask_app.util.file_util import get_file_encoding, store_request_file
guide_blueprint = Blueprint("guide_blueprint", __name__, url_prefix='/guide')


@guide_blueprint.before_request
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


@guide_blueprint.route('', methods=['GET'])
@handle_error
def get_guide_system():
    '''
    有cid, 返回指定操作指导系统的所有步骤的配置项
    无cid, 返回所有操作指导系统及其步骤实时完成情况
    '''
    have_id, data = get_request_data(request, ['cid'])
    if have_id:
        _, page, size = check_page(request)
        guide_sys, all_steps, total_steps = OperGuideSystem.get_guide_sys_by_id(data['cid'], g.unit, page, size)
        guide_sys['total'] = total_steps
        guide_sys['steps'] = [s.to_json() for s in all_steps]
        if not guide_sys:
            return false_return('找不到指定操作指导系统')
        return true_return('查询成功', guide_sys)

    have_page, page, size = check_page(request)
    if have_page:
        guide_systems, total = OperGuideSystem.get_guide_systems_by_page(g.unit, page, size)
    else:
        guide_systems, total = OperGuideSystem.get_all_guide_systems(g.unit)

    guide_systems = [g.to_json() for g in guide_systems]
    for guide_sys in guide_systems:
        # 此处不分页，需要获取该系统下所有的step
        gsystem, all_steps, _ = OperGuideSystem.get_guide_sys_by_id(guide_sys['cid'], g.unit)

        # all_steps = gsystem['steps']
        all_steps = [s.to_json() for s in all_steps]
        _, failure_steps, total_steps = get_realtime_value(all_steps)

        guide_sys['failure_steps'] = failure_steps
        guide_sys['total_steps'] = total_steps
        guide_sys['status'] = failure_steps == 0

    result = {
        'total': total,
        'guide_systems': guide_systems
    }
    return true_return('查询成功', result)


@guide_blueprint.route('/guide_systems', methods=['GET'])
@handle_error
def get_all_guide_systems():
    guide_systems, _ = OperGuideSystem.get_all_guide_systems(g.unit)
    return true_return('查询成功', {'guide_systems': [g.to_json() for g in guide_systems]})



@guide_blueprint.route('/upload_sys_file', methods=['POST'])
@handle_error
def upload_sys_file():
    try:
        success , msg = check_unit()
        if not success:
            false_return(msg)
        tags_desc_file = request.files['oper_sys_file']
        if tags_desc_file:
            allowed, filename, extension = allowed_upload_csv(tags_desc_file.filename, allowed_extensions=['xlsx'])
            if not allowed:
                error_message = "文件后缀名必须是.xlsx"
                return false_return(error_message)
            path = store_request_file(tags_desc_file, filename, prefix="_oper_sys_file", extension='xlsx')
            print(filename, extension)
            encoding = get_file_encoding(path)
            
            batch_create_oper_guide_sys_by_file(path, g.unit, encoding=encoding)
            return true_return("文件上传成功")
        return false_return("请选择文件")
    except UnicodeDecodeError as decode_error:
        traceback.print_exc()
        return false_return('文件编码错误,无法解析,文件编码格式应为UTF-8 或 GBK 或 GB2312')
    except Exception as e:
        traceback.print_exc()
        return false_return('xlsx文件中需要有系统中文名和系统英文名, 文件编码(encoding) 需要为UTF-8 或 GBK 或 GB2312 ')

def batch_create_oper_guide_sys_by_file(file,unit, encoding='utf-8', check=True):
    data: pd.DataFrame = pd.read_excel(file)
    for sys_chinese_name, sys_english_name in zip(data['系统中文名'].values, data['系统英文名'].values):
        OperGuideSystem.create_guide_system(sys_english_name,sys_chinese_name, unit)
						
def batch_create_oper_guide_step_by_file(file,user_id, gsysid, unit, encoding='utf-8', check=True):
    data: pd.DataFrame = pd.read_excel(file)
    for step_desc,step_name,order,actual ,judge, trigger ,display in zip(
                                                  data['步骤名称'].values,
                                                  data['步骤英文名称'].values,
                                                  data['步骤排序'].values,
                                                  data['实际值'].values,
                                                  data['判定条件'].values,
                                                  data['触发条件'].values,
                                                  data['显示值'].values):
        OperGuideStep.create_step( step_desc=step_desc,step_name=step_name,order=int(order), judge=judge, trigger=trigger, display=display, actual=actual,  guide_system =gsysid,force_done=False, user_id=user_id, unit=unit)


@guide_blueprint.route('/upload_step_file', methods=['POST'])
@auth.login_required
@handle_error
def upload_step_file():
    try:
        gsysid = request.args['gsysid']
        if not gsysid:
            false_return('请输入操作指导系统id')

        tags_desc_file = request.files['oper_step_file']
        if tags_desc_file:
            allowed, filename, extension = allowed_upload_csv(tags_desc_file.filename, allowed_extensions=['xlsx'])
            if not allowed:
                error_message = "文件后缀名必须是.xlsx"
                return false_return(error_message)
            path = store_request_file(tags_desc_file, filename, prefix="_oper_guide_file", extension='xlsx')
            print(filename, extension)
            encoding = get_file_encoding(path)
            batch_create_oper_guide_step_by_file(path,gsysid=gsysid, user_id=g.user.uid,unit=g.unit, encoding=encoding)
            return true_return("文件上传成功")
        return false_return("请选择文件")
    except UnicodeDecodeError as decode_error:
        traceback.print_exc()
        return false_return('文件编码错误,无法解析,文件编码格式应为UTF-8 或 GBK 或 GB2312')
    except Exception as e:
        traceback.print_exc()
        return false_return('xlsx文件中需要有"步骤名称,步骤英文名称,步骤排序,实际值,判定条件,触发条件,显示值等列, 文件编码(encoding) 需要为UTF-8 或 GBK 或 GB2312 ')


@guide_blueprint.route('/download_sys_file', methods=['GET'])
@handle_error
def download_sys_file():
    # 系统数据比较少，暂时不做分页
    sys_name = g.data.get('system_name', None)
    sys_alias = g.data.get('system_alias', None)
    all_unit = g.data.get("all_unit", False)
    
    all_unit = to_bool(all_unit)
    
    return_sys, size = OperGuideSystem.search_all(sys_name=sys_name, sys_alias=sys_alias, 
                                                  unit=g.unit, all_unit=all_unit)
    if size:
        out = io.BytesIO()
        filename = str(datetime.date.today()) + 'oper_guide_system_download.xlsx'
        return_sys = format_sys_data(return_sys)
        return_sys = pd.DataFrame(return_sys)
        return_sys.to_excel(out, index=False)
        
        out.seek(0)
        response = make_response(out.getvalue())
        response.headers['Content-Type'] = 'application/x-xlsx'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Content-Disposition'] = 'attachment; filename=' + filename
        return response
    else:
        return false_return('no data', None)


def format_sys_data(data: list) -> dict:
    return_sys = {
        '系统中文名': [],
        '系统英文名': [],
    }
    for sys in data:
        return_sys['系统中文名'].append(sys.alias)
        return_sys['系统英文名'].append(sys.name)
    return return_sys


@guide_blueprint.route('/download_step_file', methods=['GET'])
@handle_error
def download_step_file():
    # _, page, size = check_page(request)
    # 同一系统的操作步骤无需分页
    step_name = g.data.get('step_name', None)
    step_desc = g.data.get('step_desc', None)
    all_unit = g.data.get('all_unit', False)
    sys = g.data.get('guide_system', None)
    
    all_unit = to_bool(all_unit)
    try:
        sys = int(sys)
    except Exception as e:
        print('参数guide_system类型错误: ', str(e))
        return false_return('参数guide_system类型错误或未传入, 请传入合适的值.', None)
    
    return_steps, size = OperGuideStep.search_all(step_name=step_name, step_desc=step_desc, unit=g.unit, 
                                                  guide_system=sys, all_unit=all_unit)
    if size:
        out = io.BytesIO()
        filename = str(datetime.date.today()) + 'oper_guide_step_download.xlsx'
        return_steps = format_step_data(return_steps)
        return_steps = pd.DataFrame(return_steps)
        return_steps.to_excel(out, index=False)
        
        out.seek(0)
        response = make_response(out.getvalue())
        response.headers['Content-Type'] = 'application/x-xlsx'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Content-Disposition'] = 'attachment; filename=' + filename
        return response
    else:
        return false_return('no data', None)


def format_step_data(data: list) -> dict:
    return_steps = {
        '步骤名称': [],
        '步骤英文名称': [],
        '步骤排序': [],
        '实际值': [],
        '判定条件': [],
        '触发条件': [],
        '显示值': []
    }
    for step in data:
        return_steps['步骤名称'].append(step.step_desc)
        return_steps['步骤英文名称'].append(step.step_name)
        return_steps['步骤排序'].append(step.display_order)
        return_steps['实际值'].append(step.actual)
        return_steps['判定条件'].append(step.judge)
        return_steps['触发条件'].append(step.trigger)
        return_steps['显示值'].append(step.display)
    return return_steps


@guide_blueprint.route('', methods=['POST'])
@handle_error
def add_guide_system():
    success, data = get_request_data(request, ['name', 'alias'])
    if not success:
        return false_return(data)
    
    guide_sys_name = data['name']
    guide_sys_alias = data['alias']

    OperGuideSystem.create_guide_system(guide_sys_name, guide_sys_alias, g.unit)
    return true_return('新增操作指导系统成功')


@guide_blueprint.route('', methods=['PUT'])
@handle_error
def modify_guide_system():
    success, data = get_request_data(request, ['cid'])
    if not success:
        return false_return(data)
    
    cid = data['cid']
    guide_sys, _, _ = OperGuideSystem.get_guide_sys_by_id(cid, g.unit, need_steps=False)
    if not guide_sys:
        return false_return('找不到指定操作指导系统')

    update_data = dict()
    if 'name' in g.data:
        update_data['name'] = g.data['name']
    if 'alias' in g.data:
        update_data['alias'] = g.data['alias']

    OperGuideSystem.update_guide_system(cid, update_data)
    return true_return('修改成功')


@guide_blueprint.route('', methods=['DELETE'])
@handle_error
def delete_guide_system():
    success, data = get_request_data(request, ['cids'])
    if not success:
        return false_return(data)
    
    try:
        cids = json.loads(data['cids'])
    except:
        return false_return('cids格式不正确')

    for cid in cids:
        guide_sys, all_steps, _ = OperGuideSystem.get_guide_sys_by_id(cid, g.unit)
        if not guide_sys:
            return false_return('找不到操作指导系统 cid-{}'.format(cid))
        
        # gsids = [s['pid'] for s in guide_sys['steps']]
        gsids = [s.gsid for s in all_steps]
        OperGuideStep.delete_steps(gsids)
        OperGuideSystem.delete_guide_system(cid)
    return true_return('删除成功')


def get_realtime_value(all_steps):
    ts = redis.read('latest')
    CDATA = None
    if ts:
        ts = int(ts)
        # 向前最多寻找定时任务周期三倍时间内的CDATA
        for offset in range(_get_config.POINT_CHECK_CYCLE * 3):
            CDATA_key = '{}-CDATA'.format(ts - offset)
            if result_redis.redis_client.exists(CDATA_key):
                CDATA = result_redis.hgetall(CDATA_key)
                break
    if CDATA is None and result_redis.redis_client.exists('CDATA-latest'):
        CDATA = result_redis.read('CDATA-latest')

    results = list()
    # if CDATA is None:
    #     return results, 0, 0

    n_failure = 0
    total = 0
    for step in all_steps:
        res = {
            'pid': step['pid'],
            'step_name': step['step_name'],
            'step_desc': step['step_desc'],
            'actual': '',
            'aim': '',
            'done': True,
            'display_order': step['display_order'],
            'force_done': step['force_done'],
            'force_done_time': step['force_done_time'],
            'force_done_user': step.get('force_done_user')
        }

        if CDATA is not None and step['step_name'] in CDATA:
            step_realtime_val = json.loads(CDATA[step['step_name']])
            if type(step_realtime_val) != type({}):
                break
            res['actual'] = step_realtime_val['actual']
            res['aim'] = step_realtime_val['aim']
            res['done'] = step_realtime_val['done']
        
        results.append(res)
        if not res['done']:
            n_failure += 1
        total += 1
    
    return results, n_failure, total


@guide_blueprint.route('/step', methods=['GET'])
# @handle_error
def get_guide_steps():
    '''
    传入cid获取指定系统下所有步骤的实时信息
    传入pid获取指定步骤的配置信息
    '''
    if 'cid' in g.data:
        cid = g.data['cid']
        _, page, size = check_page(request)
        guide_sys, all_steps, total_steps = OperGuideSystem.get_guide_sys_by_id(cid, g.unit, page, size)
        if not guide_sys:
            return false_return('找不到指定的操作指导系统')
        
        # all_steps = guide_sys['steps']
        all_steps = [s.to_json() for s in all_steps]
        results, _, _ = get_realtime_value(all_steps)
        res = {
            'steps': results,
            'total': total_steps
        }
        # results['total'] = total_steps
        
        return true_return('查询成功', res)
    
    if 'pid' in g.data:
        gsid = g.data['pid']
        step = OperGuideStep.get_by_id(gsid, g.unit)
        if not step:
            return false_return('找不到指定操作指导步骤')
        return true_return('查询步骤配置信息成功', step.to_json(full=False))
    
    return false_return('缺少cid或pid')


@guide_blueprint.route('/step', methods=['POST'])
@handle_error
@auth.login_required
def add_guide_step():
    success, data = get_request_data(request, ['cid', 'step_name', 'step_desc'])
    if not success:
        return false_return(data)

    cid = data['cid']
    parent_sys, _, _ = OperGuideSystem.get_guide_sys_by_id(cid, g.unit, need_steps=False)
    if not parent_sys:
        return false_return('找不到指定操作指导系统')

    step_name = data['step_name']
    existed_step = OperGuideStep.get_by_name(step_name)
    if existed_step:
        return false_return('步骤英文名重复')
    
    step_desc = data['step_desc']
    actual = g.data.get('actual')
    judge = g.data.get('judge')
    display = g.data.get('display')
    trigger = g.data.get('trigger')
    order = g.data.get('display_order')

    if order and order <= 0:
        return false_return('步骤排序必须大于0')

    success, msg = OperGuideStep.create_step(step_name, step_desc, judge, trigger, display, actual, order, cid,
                                             parent_sys['force_done'], g.user.uid, g.unit)
    # PointDesc.create_point(step_name, step_desc, judge, None, display, None, trigger, None, None, [s_name], None, None, actual, order)
    if not success:
        return false_return(msg)
    
    return true_return('新增步骤成功')


@guide_blueprint.route('/step', methods=['PUT'])
@handle_error
def modify_guide_step():
    success, data = get_request_data(request, ['pid'])
    if not success:
        return false_return(data)
    
    pid = data['pid']
    tmp = OperGuideStep.get_by_id(pid, g.unit)
    if tmp is None:
        return false_return('找不到指定操作指导步骤')
    
    update_data = dict()
    if 'step_name' in g.data:
        update_data['step_name'] = g.data['step_name']
    if 'step_desc' in g.data:
        update_data['step_desc'] = g.data['step_desc']
    if 'judge' in g.data:
        update_data['judge'] = g.data['judge']
    if 'trigger' in g.data:
        update_data['trigger'] = g.data['trigger']
    if 'display' in g.data:
        update_data['display'] = g.data['display']
    if 'display_order' in g.data:
        update_data['display_order'] = int(g.data['display_order'])
    if 'actual' in g.data:
        update_data['actual'] = g.data['actual']

    OperGuideStep.update_step(pid, update_data)
    return true_return('修改成功')


@guide_blueprint.route('/guide_force_done', methods=['PUT'])
@handle_error
@auth.login_required
def force_done_system():
    success, data = get_request_data(request, ['cid', 'done'])
    if not success:
        return false_return(data)
    
    cid = data['cid']
    done = data['done']
    target_sys, all_steps, _ = OperGuideSystem.get_guide_sys_by_id(cid, g.unit, need_steps=True)
    if not target_sys:
        return false_return('找不到指定操作指导系统')
    
    OperGuideSystem.force_to_done_system(cid, done)
    # effected_steps_id = [s['pid'] for s in target_sys['steps']]
    effected_steps_id = [s.gsid for s in all_steps]
    OperGuideStep.force_to_done_steps(effected_steps_id, g.user.uid, done)
    
    res_msg = '屏蔽成功' if done else '解除屏蔽成功'
    return true_return(res_msg)


@guide_blueprint.route('/step_force_done', methods=['PUT'])
@handle_error
@auth.login_required
def force_done_step():
    success, data = get_request_data(request, ['pids', 'done'], ['pids'])
    if not success:
        return false_return(data)
    
    operate_user = g.user.uid
    if not operate_user:
        return false_return('无法获得用户信息')
    
    gsids = data['pids']
    done = data['done']
    # target_step = OperGuideStep.get_by_id(gsid, g.unit)
    # if not target_step:
    #     return false_return('找不到指定操作指导步骤')
    
    OperGuideStep.force_to_done_steps(gsids, g.user.uid, done)
    res_msg = '屏蔽成功' if done else '解除屏蔽成功'
    return true_return(res_msg)


@guide_blueprint.route('/step', methods=['DELETE'])
@handle_error
def delete_guide_steps():
    success, data = get_request_data(request, ['pids'])
    if not success:
        return false_return(data)
    
    try:
        pids = json.loads(data['pids'])
    except:
        return false_return('pids格式不正确')
        
    for pid in pids:
        tmp = OperGuideStep.get_by_id(pid, g.unit)
        if tmp is None:
            return false_return('找不到操作指导步骤 {}'.format(pid))
    OperGuideStep.delete_steps(pids)

    return true_return('删除成功')


@guide_blueprint.route('/test_guide_websocket', methods=['GET'])
def test_guide_websocket():
    from flask_app.common.send_websocket_msg import send_websocket_msg
    
    web_socket_data = {
        'step_id': 1,
        'guide_system_id': 1,
    }

    send_websocket_msg('guidance', web_socket_data, broadcast=False, room=str(g.unit))
    return true_return('websocket已发送')
