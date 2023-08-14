import json
import io
import os

import xlsxwriter
from flask import g, request, make_response
from flask_app import redis
from flask_app.api import handle_error
from flask_app.common.before_request import (check_page, get_border,
                                             get_request_data)
from flask_app.common.constants import ModelStatus
from flask_app.common.result import false_return, true_return
from flask_app.common.send_websocket_msg import send_websocket_msg
from flask_app.models.algorithm import Algorithm
from flask_app.models.dataset import Dataset
from flask_app.models.model import Model
from flask_app.models.model_timer import Model_timer
from flask_app.models.system_config import SystemConfig
from flask_app.util.common.file_os import tail_file
from flask_app.util.common.time_trans import *
from flask_app.util.str_util import to_bool
from flask_app.util.token_auth import auth

from . import check_model_and_args, model_blueprint


@model_blueprint.route('/multi_search', methods=['GET'])
def multi_search():
    # mid = g.data.get('mid')
    # p = multiprocessing.Process(group=None, target=train_model_test, args=(mid,))
    # p.start()
    have_page, left, right = get_border(request)
    # have_page, page, size = check_page(request)

    need_keys = g.data.get('fields', None)
    if need_keys:
        try:
            need_keys = need_keys.strip().split(',')
        except:
            return false_return('"fields"解析失败')

    version = g.data.get('version', None)
    name = g.data.get('name', None)
    yname = g.data.get('yname', None)
    category = g.data.get('category', None)
    dataset = g.data.get('dataset', None)
    sub_system = g.data.get('sub_system', None)
    status = g.data.get('status', None)
    train_method_name = g.data.get('train_method', None)
    is_warning = g.data.get('is_warning', None)
    latest = g.data.get('latest', True)  # 默认返回最新版本

    if is_warning:
        is_warning = to_bool(is_warning)
    latest = to_bool(latest)

    return_models, total = Model.search_all(g.unit, version, name, category, yname, dataset, sub_system, 
                                            status, train_method_name, is_warning, latest=latest)


    if  have_page:
        return_models = return_models[left: right]

    # data = add_timer_to_json(latest_models)
    if need_keys:
        result = {
            'total': total,
            'models': [{k: v for k, v in model.to_json().items() if k in need_keys} for model in return_models]
        }
    else:
        result = {
            'total': total,
            'models': [model.to_json() for model in return_models]
        }
    return true_return(data=result)


@model_blueprint.route('', methods=['GET'])
@auth.login_required
@handle_error
def get_model():
    data = g.data

    need_keys = None
    if 'fields' in data:
        try:
            need_keys = data['fields'].strip().split(',')
        except:
            return false_return('"fields"解析失败')
    
    if 'mid' not in data:
        # have_page, _, _ = get_border(request)
        have_page, page, size = check_page(request)
        if have_page:
            models, total = Model.get_by_page(g.unit, page, size)
        else:
            models, total = Model.get_latest(g.unit, None, None)
        
        if need_keys:
            result = {
                'total': total,
                'models': [{k: v for k, v in model.to_json().items() if k in need_keys} for model in models]
            }
        else:
            result = {
                'total': total,
                'models': [model.to_json() for model in models],
            }
        return true_return("查询成功", result)
    
    mid = data['mid']
    if 'version' in data:
        version = data['version']
        model = Model.get_by_id_and_version(mid, version, g.unit)
        if not model:
            return false_return("找不到指定模型")
        
        if need_keys:
            model_json = {k: v for k, v in model.to_json().items() if k in need_keys}
        else:
            model_json = model.to_json()
        return true_return('查询成功', model_json)
    else:
        models = Model.get_by_id(mid, g.unit)
        # result = add_timer_to_json(models)
        if need_keys:
            models_json = [{k: v for k, v in model.to_json().items() if k in need_keys} for model in models]
        else:
            models_json = [model.to_json() for model in models]
        return true_return("查询成功", models_json)




@model_blueprint.route('', methods=['POST'])
@auth.login_required
def create_model():
    # if 'unit' not in request.headers:
    #     return false_return("缺少unit")
    # g.unit = request.headers.get('unit')
    success, data = get_request_data(request, ['name', 'category'])
    if not success:
        return false_return(data)
    
    name = data['name']
    category = data['category']
    yname = data.get('yname')
    sub_system = data.get('sub_system')  # 实际上用于sysconfig的外键关联
    if category == 'detection':
        if not sub_system:
            return false_return('缺少"sub_system"')
        sub_system = int(sub_system)
        if not yname:
            yname = sub_system
    elif category == 'prediction' or category == 'regression':
        if not yname:
            return false_return('缺少"yname"')
    else:
        return false_return('非法category')
    
    mid = data.get('mid')
    version = data.get('version')
    status = data.get('status', 0)
    dataset = data.get('dataset')
    train_method = data.get('train_method')
    train = None
    if train_method:
        target_train_alg = Algorithm.get_by_id(train_method)
        if not target_train_alg:
            return false_return('找不到指定训练算法')
        train = target_train_alg.defaults
    select_method = data.get('select_method')
    optimize_method = data.get('optimize_method')
    auto_run = data.get('auto_run', 0)
    general = data.get('general','{}')
    default_general = '{}'
    if category == 'detection' and train_method:
        default_general = Algorithm.get_general_params(category, target_train_alg.name)
    elif category == 'prediction' or category == 'regression':
        default_general = Algorithm.get_general_params(category)
    default_general_json = json.loads(default_general)
    
    default_general_json.update(json.loads(general))
    general = json.dumps(default_general_json)

    if mid is None:
        mid = Model.get_last_mid() + 1
        version = 1
        # path = '/workspace/hd_ws/models/M' + str(mid) + '/v' + str(version)
    elif version is None:
        mid = int(mid)
        version = Model.get_last_version(mid=mid) + 1
        # path = '/workspace/hd_ws/models/M' + str(mid) + '/v' + str(version)
    path = '/workspace/hd_ws/models/M{}/v{}'.format(mid, version)

    if category == 'detection':
        status = 4  # 跳过特征选择
    
    if sub_system:
        target_system = SystemConfig.get_by_id(sub_system, g.unit)
        if target_system:
            if target_system.children:
                return false_return('不支持对上级系统建模')
        else:
            return false_return(f'{g.unit}号机组 目标系统不存在')
        
    # try:
    success, msg = Model.create(
        mid=mid, name=name, version=version, category=category, path=path, status=status, yname=yname,
        dataset=dataset, train_method=train_method, train=train, select_method=select_method,
        optimize_method=optimize_method, auto_run=auto_run, general=general, sub_system=sub_system,
        user_id=g.user.uid, unit=g.unit
    )
    if not success:
        return false_return(msg)

    Model_timer.create(mid=mid, version=version)


    # except:
        # return false_return(data=data, msg='添加失败')
    data = {
        'mid': mid,
        "version": version
    }
    return true_return(data=data, msg='添加成功')


@model_blueprint.route('', methods=['PUT'])
@handle_error
def update_model():
    success, data = get_request_data(request, ['mid', 'version'])
    if not success:
        return false_return(data)
    mid = data['mid']
    version = data['version']
    model = Model.get_by_id_and_version(mid=mid, version=version, unit=g.unit)
    if model is None:
        return false_return('模型不存在')
    
    update_data = dict()
    # 比对找出需要更新的字段
    for attr, val in model.to_json().items():
        if attr in data and data[attr] != val:
            update_data[attr] = data[attr]

    # 检查数据集在磁盘上是否存在
    if 'dataset' in update_data:
        did = update_data['dataset']
        target_dataset = Dataset.get_by_id(did)
        if not target_dataset:
            return false_return('找不到指定数据集')
        
        if not os.path.exists(target_dataset.path):
            return false_return('指定数据集不存在，请更换数据集')

    # 检查算法是否存在
    def check_alg_param(method_field, model_field, param_field):
        nonlocal model, update_data, data
        aid = data[method_field]
        target_alg = Algorithm.get_by_id(aid)
        if not target_alg:
            return False, '指定算法<aid-{}>不存在'.format(aid)
        if target_alg.category != model.category:
            return False, '算法与模型所属类别不匹配！'
        update_data[method_field] = data[method_field]
        # 若模型未设定对应算法参数且当前接口未收到参数更新信息，则将算法默认参数设定到模型参数中
        if model_field is None and not (param_field in data and data[param_field]):
            update_data[param_field] = target_alg.defaults
        return True, ''
    
    for args in (
        ('select_method', model.selection, 'selection'),
        ('train_method', model.train, 'train'),
        ('optimize_method', model.optimization, 'optimization')
    ):
        if args[0] in data:
            if model.category == 'detection' and args[0] == 'select_method':
                continue
            check_success, res_data = check_alg_param(*args)
            if not check_success:
                return false_return(res_data)
    
    # 为异常检测模型填入默认的general参数（可待优化）
    if model.category == 'detection' and (model.train_method or 'train_method' in update_data):
        target_aid = update_data.get('train_method', model.train_method)
        detection_alg = Algorithm.get_by_id(target_aid)
        if not detection_alg:
            return false_return('模型训练算法不存在')
    
    if model.status == ModelStatus.SETTING_UP:
        update_data['status'] = ModelStatus.SET_UP_DONE
    
    if not update_data:
        return true_return("未修改任何参数")
    
    Model.update_model(mid, version, update_data)

    return true_return('修改成功')


@model_blueprint.route('/selected_features', methods=['POST'])
@check_model_and_args(required=['features'])
def add_selected_features():
    target_model: Model = g.model
    mid = target_model.mid
    version = target_model.version
    
    features_str = g.data['features']
    features_add = list(map(lambda x: x.strip(), features_str.split(',')))
    print('features_add:', features_add)

    success, err_msg = check_point_name_in_redis(features_add)
    if not success:
        return false_return(err_msg)


    new_features = None
    if not target_model.selected_features:
        new_features = features_add
    else:
        try:
            new_features = eval(target_model.selected_features)
        except:
            return false_return('模型select_features字段格式错误')
        new_features.extend(features_add)
    
    if new_features:
        Model.update_model(mid, version, {'selected_features': str(new_features)}, print_data=False)
    return true_return('特征批量增加成功！')


def check_point_name_in_redis(point_names: list):
    all_points = redis.read('all_points')
    if not all_points:
        return False, '实时点名列表获取失败！'
    all_points = set(all_points.split(','))

    not_founds = [f for f in point_names if f not in all_points]
    if len(not_founds) > 0:
        return False, '点 {} 在实时数据中无法找到'.format(','.join(not_founds))
    return True, ''


@model_blueprint.route('/selected_features', methods=['PUT'])
@check_model_and_args(required=['features'], list_fields=['features'])
def modify_selected_features():
    model: Model = g.model
    new_features = g.data['features']
    
    Model.update_model(model.mid, model.version, {'selected_features': str(new_features)}, print_data=False)
    return true_return('修改成功')


def remove_model_from_processes(mid, version):
    '''
    将指定模型从任务队列中移除
    '''
    import signal

    from flask_app.util.process_manager import (optimize_processes,
                                                optimizing_processes,
                                                select_processes,
                                                train_processes,
                                                training_processes)
    
    for queue in (optimize_processes, optimizing_processes, select_processes,
                  train_processes, training_processes):
        target_pid = queue.pop((mid, version), None)
        if target_pid is not None:
            try:
                os.kill(target_pid, signal.SIGKILL)
            except ProcessLookupError or TypeError:
                print('[{}] <Model {}, {}>(pid: {}) kill error'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), mid, version, target_pid))


@model_blueprint.route('', methods=['DELETE'])
@handle_error
def delete_model():
    from flask_app.api.model_api.lifetime import delete_running_flags

    success, data = get_request_data(request, ['mid'])
    if not success:
        return false_return(data)

    mid = int(data['mid'])
    version = int(g.data.get('version', 0))  # version == 0删除当前mid所有版本的模型
    
    if version:
        target: Model = Model.get_by_id_and_version(mid, version, g.unit)
        if not target:
            return false_return('找不到指定模型')
        
        if target.status == ModelStatus.RUNNING:
            delete_running_flags(mid, version)
        
        remove_model_from_processes(mid, version)
        Model.delete(mid, version)
        Model_timer.delete(mid, version)
    else:
        models = Model.get_by_id(mid=mid, unit=g.unit)
        if not models:
            return false_return('模型不存在')

        versions = [model.version for model in models]
        for version in versions:
            remove_model_from_processes(mid, version)
            delete_running_flags(mid, version)
            Model.delete(mid, version)
            Model_timer.delete(mid, version)
            # del_dir_file(model.save_path)
    return true_return(msg='删除成功')


@model_blueprint.route('/statistic', methods=['GET'])
def statistic_category():
    success, data = get_request_data(request, ['classification'])
    if not success:
        return false_return(data)
    classification = data['classification']
    if classification != 'category' and classification != 'status':
        return false_return("统计方法有误，必须是category或者status")
    statistics = Model.statistic_category(classification, g.unit)
    return true_return("按" + classification + "统计成功", statistics)


@model_blueprint.route('/logs', methods=['GET'])
def get_model_logs():
    success, data = get_request_data(request, ['mid', 'version', 'stage', 'type'])
    if not success:
        return false_return(data)
    
    mid = data['mid']
    version = data['version']
    target_model: Model = Model.get_by_id_and_version(mid, version, g.unit)
    if not target_model:
        return false_return('找不到指定模型')
    
    stage = data['stage']  # ['selection', 'train', 'optimization']
    if stage not in ('selection', 'train', 'optimization', 'run'):
        return false_return('stage参数非法')

    log_type = data['type']  # ['std', 'err']
    if log_type == 'std':
        type_str = ''
    elif log_type == 'err':
        type_str = '_err'
    else:
        return false_return('type参数非法')
    
    model_path = target_model.save_path
    # model_path = '/workspace/hd_ws/models/M{}/v{}'.format(mid, version)
    log_path = os.path.join(model_path, 'logs', '{}{}.log'.format(stage, type_str))
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



@model_blueprint.route('/test_eval_websocket', methods=['POST'])
def get_eval_websocket():
    web_socket_data = {
        'mid': 24,
        'version': 3,
        'ts': 1640944084,
        'mse': 1.1460216932207666e-06,
        'real_mse': 0.9031842513095525,
        'warning_gate': 2.0
    }

    send_websocket_msg('realtime_evaluate', web_socket_data, broadcast=False, room=str(g.unit))
    return true_return('websocket已发送')


@model_blueprint.route('/test_updates', methods=['POST'])
def test_multi_updates():
    success, data = get_request_data(request, ['data'], ['data'])
    if not success:
        return false_return(data)
    updates_args = data['data']
    Model.update_models(updates_args)
    return true_return('更新成功')


@model_blueprint.route('/export_model_info', methods=['GET'])
def export_models_to_file():
    name = g.data.get('name', None)
    yname = g.data.get('yname', None)
    category = g.data.get('category', None)
    dataset = g.data.get('dataset', None)
    sub_system = g.data.get('sub_system', None)
    status = g.data.get('status', None)
    train_method_name = g.data.get('train_method', None)
    latest = g.data.get('latest', True)  # 默认返回最新版本
    all_unit = g.data.get('all_unit', False)
    
    latest = to_bool(latest)
    all_unit = to_bool(all_unit)

    return_models, _ = Model.search_all(g.unit, None, name, category, yname, dataset, sub_system, 
                                            status, train_method_name, None, latest=latest, all_unit=all_unit)

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    sheet1 = workbook.add_worksheet()
    titles = [
        '模型名称', '目标点', '模型类型', '异常检测目标系统', '输入时间长度', 
        '预测时间长度', '数据集名称', '特征选择算法', '特征选择个数', '手动输入特征', 
        '训练算法', '调优算法', '调优次数', '训练设备'
    ]
    # formats = {'font-size': 11}
    widths = [28, 18.33, 8.17, 18.33, 12.17, 12.17, 17, 14, 11.83, 24, 16.67, 21.67, 8, 8]
    for ti, title in enumerate(titles):
        sheet1.write(0, ti, title)
        sheet1.set_column(ti, ti, width=widths[ti])
    
    for i, model in enumerate(return_models):
        model_info = model.to_json()
        sheet1.write(i + 1, 0, model_info['name'])
        sheet1.write(i + 1, 1, model_info['yname'])

        category_name_map = {
            'prediction': '实时预测',
            'regression': '回归分析',
            'detection': '异常检测'
        }
        sheet1.write(i + 1, 2, category_name_map[model_info['category']])

        psystem = ''
        if model.psystem is not None:
            target_system: SystemConfig = SystemConfig.get_by_id(model.psystem, model.unit)
            if target_system:
                psystem = target_system.alias
        sheet1.write(i + 1, 3, psystem)

        general_params = model_info['general']
        input_window = ''
        pred_horizon = ''
        if isinstance(general_params, dict):
            input_window = general_params.get('window', '模型参数有误')
            pred_horizon = general_params.get('horizon', '模型参数有误')
        sheet1.write(i + 1, 4, input_window)
        sheet1.write(i + 1, 5, pred_horizon)

        dataset_name = ''
        if model.dataset is not None:
            dataset: Dataset = Dataset.get_by_id(model.dataset)
            if dataset:
                dataset_name = dataset.name
        sheet1.write(i + 1, 6, dataset_name)

        def get_alg_name(aid):
            alg_name = ''
            if aid is not None:
                target_alg: Algorithm = Algorithm.get_by_id(aid)
                if target_alg:
                    alg_name = target_alg.chinese_name
            return alg_name
        
        sheet1.write(i + 1, 7, get_alg_name(model.select_method))

        model_features = model_info['selected_features']
        sheet1.write(i + 1, 8, len(model_features))
        if isinstance(model_features, list):
            model_features_str = ','.join(model_features)
        else:
            model_features_str = model_features
        sheet1.write(i + 1, 9, model_features_str)

        sheet1.write(i + 1, 10, get_alg_name(model.train_method))

        sheet1.write(i + 1, 11, get_alg_name(model.optimize_method))
        
        sheet1.write(i + 1, 13, 'cuda:0')  # 训练设备
    
    workbook.close()
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'application/x-xlsx'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Content-Disposition'] = 'attachment; filename=model_exports.xlsx'
    return response
