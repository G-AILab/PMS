import json
import multiprocessing
import os
import pickle
import random
import signal
import time
import traceback

from flask import current_app, g, request
# from hd.operate import (compare, evaluate, feature_select, load_model,optimize)
# from hd.operate import train as model_train
from loguru import logger
from pebble import ProcessPool

import flask_app.util.process_manager as process_manager
from flask_app import _get_config, db, redis, result_redis, flask_app
from flask_app.api import handle_error
from flask_app.common.before_request import get_request_data
from flask_app.common.constants import ModelStatus
from flask_app.common.get_scores import (get_res, get_score)
from flask_app.common.result import false_return, true_return
from flask_app.common.send_websocket_msg import send_websocket_msg
from flask_app.models.algorithm import Algorithm
from flask_app.models.dataset import Dataset
from flask_app.models.model import Model
from flask_app.models.model_timer import Model_timer
from flask_app.models.system_config import SystemConfig
from flask_app.util.str_util import to_bool
from flask_app.util.token_auth import auth
from flask_app.util.json_encoder import JsonEncoder
from . import check_model_and_args, model_blueprint, find_features_existed


@model_blueprint.route('/processes', methods=['GET'])
def get_processes():
    '''
    返回系统中创建的进程
    '''
    success, data = get_request_data(request, ['type'])
    if not success:
        return false_return(data)

    query_type = data['type']
    scope = ['train', 'select', 'optimize', 'auto_run', 'all']
    if query_type == 'train':
        from flask_app.util.process_manager import (train_processes,
                                                    training_processes)
        res = {
            'waiting': dict(train_processes),
            'training': dict(training_processes)
        }
    elif query_type == 'select':
        from flask_app.util.process_manager import select_processes
        res = {
            'selecting': dict(select_processes)
        }
    elif query_type == 'optimize':
        from flask_app.util.process_manager import (optimize_processes,
                                                    optimizing_processes)
        res = {
            'waiting': dict(optimize_processes),
            'optimizing': dict(optimizing_processes)
        }
    elif query_type == 'auto_run':
        from flask_app.util.process_manager import (auto_run_processes,
                                                    auto_waiting_processes)
        res = {
            'waiting': dict(auto_waiting_processes),
            'auto_running': dict(auto_run_processes)
        }
    elif query_type == 'all':
        from flask_app.util.process_manager import (select_processes,
                                                    select_wait_processes,
                                                    train_processes,
                                                    training_processes,
                                                    optimize_processes,
                                                    optimizing_processes)
        res = {
            'select_wait_processes': dict(select_wait_processes),
            'select_processes': dict(select_processes),
            'train_processes': dict(train_processes),
            'training_processes': dict(training_processes),
            'optimize_processes': dict(optimize_processes),
            'optimizing_processes': dict(optimizing_processes)
        }
    else:
        res = '未识别的type。可用的type: {}'.format(scope)

    if isinstance(res, dict):
        res_trans = dict()
        for tp in res.keys():
            res_trans[tp] = dict()
            for k, v in res[tp].items():
                res_trans[tp][str(k)] = v
    else:
        res_trans = res

    # print(select_processes)
    # print(res_trans)
    return true_return('查询成功', res_trans)


@model_blueprint.route('/pop_processes', methods=['POST'])
def pop_model_from_processes():
    operations = g.data.get('operation')
    # success, data = get_request_data(request, ['operation'])
    if operations is None:
        return false_return('"operation"未填写')

    from flask_app.util import process_manager as pm

    model_updates = list()
    for oper in operations:
        """ example of "oper"
        {
            'target': 'select_wait_processes',
            'mid': 1,
            'version': 1
        }
        """
        if not hasattr(pm, oper['target']):
            logger.warning('wrong processes list target: {}'.format(oper['target']))
            continue

        processes = getattr(pm, oper['target'])
        mid, version = oper['mid'], oper['version']
        processes.pop((oper['mid'], oper['version']), None)

        if oper['target'] in ('select_wait_processes', 'select_processes'):
            new_status = ModelStatus.SELECTING_ERROR
        elif oper['target'] in ('train_processes', 'training_processes'):
            new_status = ModelStatus.TRAINING_ERROR
        elif oper['target'] in ('optimize_processes', 'optimizing_processes'):
            new_status = ModelStatus.OPTIMIZING_ERROR
        else:
            continue
        model_updates.append({'mid': mid, 'version': version, 'data': {'status': new_status}})
    Model.update_models(model_updates)

    return true_return('processes pop succeed!')


@model_blueprint.route('/add_processes', methods=['POST'])
def add_model_to_processes():
    """
        Only use for test!
    """
    success, data = get_request_data(request, ['operation'])
    if not success:
        return false_return(data)

    from flask_app.util import process_manager as pm

    operations = g.data['operation']
    for oper in operations:
        """ example of "oper"
        {
            'target': 'select_wait_processes',
            'mid': 1,
            'version': 1,
            'pid': 1
        }
        """
        if not hasattr(pm, oper['target']):
            logger.warning('wrong processes list target: {}'.format(oper['target']))
            continue
        processes = getattr(pm, oper['target'])
        mid, version = oper['mid'], oper['version']
        processes[(mid, version)] = oper['pid']
    return true_return('processes add succeed!')


@model_blueprint.route('/selection', methods=['POST'])
def select_feature():
    from flask_app.util.process_manager import select_processes
    success, data = get_request_data(request, ['mid', 'version'])
    if not success:
        return false_return(data)
    mid = data['mid']
    version = data['version']
    target_model = Model.get_by_id_and_version(mid, version, g.unit)
    if not target_model:
        return false_return('找不到指定模型')

    if (mid, version) in select_processes:
        return false_return('模型已在特征选择中！')

    num = int(data.get('num', 30))  # 特征选择个数
    # print("更新模型状态")
    Model.update_model(mid, version, {'status': ModelStatus.SELECTING})
    Model_timer.update_timer(mid, version, {'select_start': int(time.time())})

    msg = {
        "mid": mid,
        "version": version,
        "unit": g.unit,
        "num": num
    }
    redis.redis_client.xadd("msg_queue", {"select": json.dumps(msg)})

    return true_return("成功开始特征选择")


@model_blueprint.route('/selection', methods=['GET'])
@handle_error
def get_selection():
    mid = g.data.get('mid')
    version = g.data.get('version')
    model = Model.get_by_id_and_version(mid, version, unit=g.unit)
    # print("API", model)
    if not model:
        return false_return('找不到指定模型')
    else:
        model_json = model.to_json()
        data = {
            'selection': model_json['selection']
        }
        return true_return("查询成功", data)


@model_blueprint.route('/selection', methods=['DELETE'])
@handle_error
def stop_selection():
    '''
    强行终止模型特征选择进程
    ----------
    Args:
        mid: 模型id
        version: 模型版本
    '''

    success, data = get_request_data(request, ['mid', 'version'])
    if not success:
        return false_return(data)

    mid = int(data['mid'])
    version = int(data['version'])

    target_pid = redis.redis_client.hget("selecting", f"M{mid}V{version}")
    try:

        if target_pid is not None:
            os.kill(target_pid, signal.SIGKILL)
            target_model: Model = Model.get_by_id_and_version(mid, version, g.unit)
            if target_model and target_model.status == ModelStatus.SELECTING:
                Model.update_model(mid, version, {'status': ModelStatus.SELECTING_ERROR})
            return true_return('指定模型未在特征选择中')

    except ProcessLookupError or TypeError:
        Model.update_model(mid, version, {'status': ModelStatus.SELECTING_ERROR})
        return false_return('特征选择任务出错')

    Model.update_model(mid, version, {'status': ModelStatus.SET_UP_DONE})

    return true_return('特征选择任务成功终止')


@model_blueprint.route('/skip_selection', methods=['POST'])
@check_model_and_args()
def skip_feature_selection():
    model: Model = g.model
    if model.status == ModelStatus.SELECTING_DONE or model.status > ModelStatus.SELECTING_ERROR:
        return false_return('特征选择已完成，无法跳过')

    if not model.selected_features:
        return false_return('特征尚未添加，无法跳过')

    Model.update_model(model.mid, model.version, {'status': ModelStatus.SELECTING_DONE})

    done_time = int(time.time())
    timer_updates = {
        'select_start': done_time,
        'select_end': done_time
    }
    Model_timer.update_timer(model.mid, model.version, timer_updates)

    return true_return('特征选择阶段跳过成功')


@model_blueprint.route('/scores', methods=['GET'])
@handle_error
def get_scores():
    success, data = get_request_data(request, ['mid', 'version'])
    if not success:
        return false_return(data)

    mid = int(data['mid'])
    version = int(data['version'])

    model: Model = Model.get_by_id_and_version(mid, version, g.unit)
    if not model:
        return false_return("模型不存在")

    if model.status != ModelStatus.SELECTING_DONE and model.status <= ModelStatus.SELECTING_ERROR:
        return false_return('模型尚未完成特征选择')

    is_selected = to_bool(data.get('is_selected', 'false'))

    # path = model.save_path + '/selection' + '/scores.pkl'
    path = os.path.join(model.save_path, 'selection', 'scores.pkl')

    if is_selected:
        score = get_score(path, features=eval(model.selected_features))
    else:
        score = get_score(path)

    return true_return('查询成功', score)  # 若score为None，则说明可能跳过了特征选择，没有产生scores.pkl


def check_model_features_in_dataset(target_model: Model, dataset: Dataset):
    success = True
    msg = ''
    try:
        dataset_points = set(json.loads(dataset.all_points))
    except:
        logger.warning('数据集 {}.{} all_points加载失败，跳过相关判断'.format(dataset.did, dataset.name))
        dataset_points = None
    if dataset_points is not None:
        features = None
        if target_model.category == 'detection':
            target_point_config = SystemConfig.get_by_id(target_model.psystem, g.unit)
            features = [p.tag_name for p in target_point_config.origin_points]
        else:
            if not target_model.selected_features:
                success = False
                msg = '模型没有被选择的特征！'
            else:
                features = eval(target_model.selected_features)
        if features is not None:
            try:
                find_features_existed(set(features), dataset_points)
            except AssertionError as ae:
                success = False
                msg = str(ae)
            except Exception as e:
                raise e
    return success, msg


@model_blueprint.route('/train', methods=['POST'])
@handle_error
def train_model_api():
    success, data = get_request_data(request, ['mid', 'version'])
    if not success:
        return false_return(data)

    from flask_app.util.process_manager import (train_processes,
                                                training_processes)
    mid = data['mid']
    version = data['version']
    target_model: Model = Model.get_by_id_and_version(mid, version, g.unit)
    if not target_model:
        return false_return('找不到指定模型版本')

    if (mid, version) in train_processes or (mid, version) in training_processes:
        return false_return('模型已处在训练状态！')

    dataset: Dataset = Dataset.get_by_id(target_model.dataset)
    if not dataset:
        return false_return('数据库中找不到指定数据集')

    existed_check_success, check_msg = check_model_features_in_dataset(target_model, dataset)
    if not existed_check_success:
        return false_return(check_msg)

    Model.update_model(mid, version, {'status': ModelStatus.TRAINING_WAIT})
    # ctx = tmp.get_context('forkserver')

    # db.get_engine(app=current_app).dispose()
    msg = {
        "mid": mid,
        "version": version,
        "unit": g.unit
    }
    redis.redis_client.xadd("msg_queue", {"train": json.dumps(msg)})
    redis.redis_client.hset("pending", f"M{mid}V{version}", time.time())

    # p = ctx.Process(target=train_model, args=(mid, version, train_processes, training_processes, g.unit))
    # train_processes.append(p.pid)
    # train_processes[(mid, version)] = p.pid
    # train_processes.append({(mid, version): p.pid})
    # p.start()
    return true_return('开始训练')



@model_blueprint.route('/train', methods=['DELETE'])
@handle_error
def stop_training():
    success, data = get_request_data(request, ['mid', 'version'])
    if not success:
        return false_return(data)

    mid = int(data['mid'])
    version = int(data['version'])

    target_pid = None
    if redis.redis_client.hexists("training", f"M{mid}V{version}"):
        target_pid = redis.redis_client.hget("training", f"M{mid}V{version}")
    elif redis.redis_client.hexists("pending", f"M{mid}V{version}"):
        target_pid = redis.redis_client.hget("pending", f"M{mid}V{version}")
    else:
        target_model: Model = Model.get_by_id_and_version(mid, version, g.unit)
        if target_model and (
                target_model.status == ModelStatus.TRAINING_WAIT or target_model.status == ModelStatus.TRAINING):
            Model.update_model(mid, version, {'status': ModelStatus.TRAINING_ERROR})
        return false_return(f'{target_model.name} 训练任务出错')

    try:
        if target_pid is not None:
            os.kill(target_pid, signal.SIGKILL)
        else:
            return true_return("该模型未在训练")
    except ProcessLookupError or TypeError:
        Model.update_model(mid, version, {'status': ModelStatus.TRAINING_ERROR})
        return false_return('训练任务出错')

    Model.update_model(mid, version, {'status': ModelStatus.SELECTING_DONE})

    return true_return('训练任务停止成功')


def select_subsystem(yname, data_path):
    # 选择子系统
    with open(data_path, 'rb') as f:
        data = pickle.load(f)
    features = data.columns
    prefix = yname.split('.')[0]
    features = [feature for feature in features if feature.startswith(prefix)]
    return features


@model_blueprint.route('/evaluation', methods=['POST'])
@handle_error
def evaluate_model():
    mid = g.data.get('mid')
    version = g.data.get('version')
    metrics = g.data.get('metrics')
    optimization = g.data.get('optimization')
    model: Model = Model.get_by_id_and_version(mid=mid, version=version, unit=g.unit)
    if not model:
        return false_return('找不到指定模型')
    import rpyc
    aps_rpc = rpyc.connect(_get_config.RPC_IP, _get_config.RPC_PORT,config={'sync_request_timeout': 5})
    results = aps_rpc.root.evaluate(model_path=model.save_path, metrics=metrics, optimization=optimization)
    if results is None:
        return true_return('模型结果不存在', None)

    origin_eval_res = model.evaluate_results
    if origin_eval_res:
        try:
            origin_eval_res = json.loads(origin_eval_res)
        except:
            origin_eval_res = json.loads(origin_eval_res.replace("'", '"'))
        new_eval_res = origin_eval_res.copy()
        if optimization:
            new_eval_res['opt'] = results
        else:
            new_eval_res['origin'] = results
    else:
        new_eval_res = {'origin': results} if optimization else {'opt': results}

    Model.update_model(mid, version, {'evaluate_results': json.dumps(new_eval_res,cls=JsonEncoder,indent=4)})

    results['res'] = {'target': [], 'pred': []}
    if not optimization:
        results['res'] = get_res(model.save_path)
    return true_return(data=results)


@model_blueprint.route('/optimization', methods=['POST'])
@handle_error
def optimize_model_api():
    success, data = get_request_data(request, ['mid', 'version', 'n_calls'])
    if not success:
        return false_return(data)

    mid = data.get('mid')
    version = data.get('version')
    n_calls = data.get('n_calls', 5)
    model = Model.get_by_id_and_version(mid=mid, version=version, unit=g.unit)
    if not model:
        return false_return("找不到指定模型")

    Model.update_model(mid, version, {'status': ModelStatus.OPTIMIZING_WAIT})

    params = model.general
    params = json.loads(params)

    params['train_params'] = json.loads(model.optimization)

    # db.get_engine(app=current_app).dispose()
    msg = {
        "mid": mid,
        "version": version,
        "n_calls": n_calls,
        "params": params,
        "unit": g.unit
    }

    redis.redis_client.xadd("msg_queue", {"optimize": json.dumps(msg)})
    redis.redis_client.hset("opt_pending", f"M{mid}V{version}", json.dumps(msg))
    return true_return('开始调优')


@model_blueprint.route('/optimization', methods=['DELETE'])
@handle_error
def stop_optimization():
    success, data = get_request_data(request, ['mid', 'version'])
    if not success:
        return false_return(data)

    mid = int(data['mid'])
    version = int(data['version'])


    target_pid = None
    if redis.redis_client.hexists("optimizing", f"M{mid}V{version}"):
        target_pid = redis.redis_client.hget("optimizing", f"M{mid}V{version}")
    elif redis.redis_client.hexists("opt_pending", f"M{mid}V{version}"):
        target_pid = redis.redis_client.hget("opt_pending", f"M{mid}V{version}")
    else:
        target_model: Model = Model.get_by_id_and_version(mid, version, g.unit)
        if target_model and (
                target_model.status == ModelStatus.TRAINING_WAIT or target_model.status == ModelStatus.TRAINING):
            Model.update_model(mid, version, {'status': ModelStatus.TRAINING_ERROR})
        return false_return(f'{target_model.name} 模型未在调优')

    try:
        if target_pid is not None:
            os.kill(target_pid, signal.SIGKILL)
    except ProcessLookupError or TypeError:
        Model.update_model(mid, version, {'status': ModelStatus.OPTIMIZING_ERROR})
        return false_return('调优任务出错')

    Model.update_model(mid, version, {'status': ModelStatus.TRAINING_DONE})

    return true_return('调优任务停止成功')


@model_blueprint.route('/skip_optimization', methods=['POST'])
@check_model_and_args()
def skip_opt():
    model: Model = g.model
    if model.status == ModelStatus.OPTIMIZING_DONE or model.status > ModelStatus.OPTIMIZING_ERROR:
        return false_return('调优已完成，无法跳过')

    if model.status != ModelStatus.TRAINING_DONE:
        return false_return('模型尚未完成训练')

    Model.update_model(model.mid, model.version, {'status': ModelStatus.OPTIMIZING_DONE})

    done_time = int(time.time())
    timer_updates = {
        'optimize_start': done_time,
        'optimize_end': done_time
    }
    Model_timer.update_timer(model.mid, model.version, timer_updates)

    return true_return('调优阶段跳过成功')


@model_blueprint.route('/test', methods=['POST'])
@handle_error
def get_test():
    import pandas as pd

    mid = g.data.get('mid')
    version = g.data.get('version')
    model = Model.get_by_id_and_version(mid=mid, version=version, unit=g.unit)
    metrics = g.data.get('metrics')
    dataset = Dataset.get_by_id(did=model.dataset)
    algorithm = Algorithm.get_by_id(aid=model.train_method)
    # model_handler = load_model(model_path=model.save_path,
    #                            model_name=algorithm.name,
    #                            category=algorithm.category)
    data = pd.read_pickle(dataset.path)
    results = ""  # TODO  test(model_handler, data, metrics)
    return true_return(data=results)


@model_blueprint.route('/compare', methods=['POST'])
def compare_models():
    mids = g.data.get('mid')
    versions = g.data.get('version')
    if len(mids) != len(versions):
        return false_return('模型列表错误')
    model_list = []
    did = g.data.get('dataset')
    metrics = g.data.get('metrics')
    dataset = Dataset.get_by_id(did=did)
    for i in range(len(mids)):
        mid = mids[i]
        version = versions[i]
        model = Model.get_by_id_and_version(mid, version, g.unit)
        algorithm = Algorithm.get_by_id(aid=model.train_method)
        # model_handler = load_model(model_path=model.save_path,
        #                            model_name=algorithm.name,
        #                            category=algorithm.category)
        # model_list.append(model_handler)
    res, res_data = "", ""  # TODO compare(model_list, dataset.path, metrics)
    data = {'res': res, 'res_data': res_data}
    return true_return(data=data)


def get_job_id(mid, version):
    # if (mid == 1) and (version == 2):
    return 'M' + str(mid) + 'V' + str(version)
    # :return 'M' + str(mid) + 'V' + str(version)


def delete_running_flags(mid, version):
    key = 'M{}V{}'.format(mid, version)
    # key = 'M' + str(mid) + 'V' + str(version)
    # result_redis.write(key, "stop")
    if result_redis.redis_client.exists(key):
        result_redis.delete(key)
    # result_redis.write(key + '_eval_flag', 'stop')
    if result_redis.redis_client.exists(key + '_eval_flag'):
        result_redis.delete(key + '_eval_flag')
    if result_redis.redis_client.exists(key + '_model'):
        result_redis.delete(key + '_model')


@model_blueprint.route('/stop_all', methods=['DELETE'])
@handle_error
def delete_all_predicting_model():
    models, total = Model.search_all(unit=g.unit)
    model_updates = list()
    model_timer_updates = list()

    stop_time = int(time.time())
    for model in models:
        if model.status == ModelStatus.RUNNING:
            model_updates.append({
                'mid': model.mid,
                'version': model.version,
                'data': {'status': ModelStatus.NOT_RUNNING}
            })
            model_timer_updates.append({
                'mid': model.mid,
                'version': model.version,
                'data': {'export_end': stop_time}
            })
            delete_running_flags(model.mid, model.version)
    Model.update_models(model_updates)
    Model_timer.update_timers(model_timer_updates)

    return true_return('全部模型停止成功')


@model_blueprint.route('/export', methods=['DELETE'])
@handle_error
def delete_predicting_model():
    success, data = get_request_data(request, ['mid', 'version'])
    if not success:
        return false_return(data)

    mid = int(data.get('mid'))
    version = int(data.get('version'))
    is_pause = data.get('pause', 'false')
    is_pause = to_bool(is_pause)
    model = Model.get_by_id_and_version(mid, version, g.unit)
    if not model:
        return false_return('找不到模型')

    if model.status != ModelStatus.RUNNING:
        return false_return('模型未在运行中')

    if not is_pause:
        Model.update_model(mid, version, {'status': 14})
    else:
        Model.update_model(mid, version, {'status': 17})
    Model_timer.update_timer(mid, version, {'export_end': int(time.time())})
    # scheduler.remove_job(id=get_job_id(mid, version))

    delete_running_flags(mid, version)
    # key = 'M' + str(mid) + 'V' + str(version)
    # # result_redis.write(key, "stop")
    # result_redis.delete(key)
    # # result_redis.write(key + '_eval_flag', 'stop')
    # if result_redis.redis_client.exists(key + '_eval_flag'):
    #     result_redis.delete(key + '_eval_flag')
    # result_redis.delete(key + '_model')

    # if model.category != 'detection' and model.status != 17:
    #     # test_job_id = '{}test'.format(get_job_id(mid, version))
    #     # if scheduler.get_job(test_job_id) is not None:
    #     #     scheduler.remove_job(id=test_job_id)
    #     # else:
    #     #     print('APS job "{}" not found!'.format(test_job_id))
    #     models_list = result_redis.read('models_list')
    #     if models_list:
    #         models_list = eval(models_list)
    #         if (mid, version) in models_list:
    #             models_list.remove((mid, version))
    #             # result_redis.write('models_list', str(models_list), expire=flask_app.config['REALTIME_EVAL_EXTIME'])
    #             result_redis.write('models_list', str(models_list), expire=_get_config.REALTIME_EVAL_EXTIME)
    #     else:
    #         logger.error('"models_list" not found!')

    return true_return('模型停止成功')


def run_one_model(model: Model, models_running: set, aid_name_map: dict, unit, opt_use=True):
    # def get_err_data(msg):
    #     return {
    #         'mid': model.mid,
    #         'version': model.version,
    #         'status': '失败',
    #         'exception': msg
    #     }
    try:
        if model is None:
            return

        yname = model.yname
        category = model.category

        # 判断是否有正在运行的模型
        if category != 'detection' and f'{yname}-{category}' in models_running:
            # send_websocket_msg('export', get_err_data(f"点 {yname} 的其他 {category} 模型正在运行"), broadcast=False, room=str(unit))
            raise RuntimeError(f"点{yname}的其他 {category} 模型正在运行")

        if model.general is None:
            # send_websocket_msg('export', get_err_data("模型general参数为空"), broadcast=False, room=str(unit))
            raise ValueError("模型general参数为空")
        params = json.loads(model.general)
        alg_name = aid_name_map[model.train_method]
        # algorithm = Algorithm.get_by_id(aid=model.train_method)

        update_dict = dict()

        if opt_use:
            file_path = os.path.join(model.save_path, 'output/opt_res/model.pkl')
            if not os.path.exists(file_path):
                # 不存在调优模型（例如跳过了调优），转为使用原模型
                opt_use = False

        opt_use = 1 if opt_use else 0
        if model.opt_use != opt_use:
            update_dict['opt_use'] = opt_use

        sub_system = model.psystem if model.category == 'detection' else 0
        # sub_system = model.sub_system if model.category == 'detection' else 0
        predict_task_provider(alg_name, model.category, model.save_path, model.mid, model.version,
                              yname, sub_system, int(params['window']), opt_use, int(unit))

        update_dict['status'] = ModelStatus.RUNNING
        Model.update_model(model.mid, model.version, update_dict, print_data=False)
        Model_timer.update_timer(model.mid, model.version, {'export_start': int(time.time())})
    except Exception:
        logger.error(f"M{model.mid}V{model.version}发布失败:" + traceback.format_exc())


def init_flask_worker():
    flask_app.app_context().push()


@model_blueprint.route('/export_all', methods=['GET'])
@auth.login_required
@handle_error
def export_all_model():
    models, total = Model.search_all(unit=g.unit)
    models_running = set()
    models_need_run = list()
    for model in models:
        if model.category != 'detection' and model.status == ModelStatus.RUNNING:
            models_running.add(f'{model.yname}-{model.category}')
        if model.status == ModelStatus.NOT_RUNNING or model.status == ModelStatus.RUNNING_PAUSE or model.status == ModelStatus.OPTIMIZING_DONE:
            models_need_run.append(model)
    aid_name_map = Algorithm.get_all_aid_name_map()
    for model in models_need_run:
        db.get_engine(app=current_app).dispose()
        logger.info(f"submit task {model}")
        try:
            process_manager.task_proc_pool.schedule(run_one_model, args=(model, models_running, aid_name_map, g.unit))
        except:
            logger.error({
                "msg": "task_proc_pool出错",
                "trace": traceback.format_exc(),
            })
            process_manager.task_proc_pool = ProcessPool(max_workers=_get_config.TASK_POOL_SIZE,
                                                         initializer=init_flask_worker, max_tasks=0,
                                                         context=multiprocessing.get_context(
                                                             'spawn'))  # ProcessPoolExecutor(max_workers=_get_config.TASK_POOL_SIZE)
            process_manager.task_proc_pool.schedule(run_one_model, args=(model, models_running, aid_name_map, g.unit))

    return true_return('已开始发布所有模型')


@model_blueprint.route('/export', methods=['POST'])
@handle_error
def export_model():
    success, data = get_request_data(request, ['mid', 'version'])
    if not success:
        return false_return(data)

    mid = data.get('mid')
    version = data.get('version')
    model: Model = Model.get_by_id_and_version(mid=mid, version=version, unit=g.unit)
    if model is None:
        return false_return('找不到模型')

    yname = model.to_json()['yname']
    category = model.to_json()['category']

    # 判断是否有正在运行的模型
    running_model = Model.get_by_yname_and_category(yname=yname, category=category, unit=g.unit)
    if running_model is not None and category != 'detection':
        return false_return('其他模型正在运行')

    algorithm = Algorithm.get_by_id(aid=model.train_method)
    params = json.loads(model.general)

    update_dict = dict()

    opt_use = data.get('opt_use', False)

    if opt_use:
        file_path = os.path.join(model.save_path, 'output/opt_res/model.pkl')
        if not os.path.exists(file_path):
            # 不存在调优模型（例如跳过了调优），转为使用原模型
            opt_use = False

    opt_use = 1 if opt_use else 0
    if model.opt_use != opt_use:
        update_dict['opt_use'] = opt_use

    warning_gate = model.warning_gate
    if 'warning_gate' in data:
        warning_gate = data['warning_gate']
        update_dict['warning_gate'] = warning_gate

    if len(update_dict) > 0:
        Model.update_model(model.mid, model.version, update_dict)

    sub_system = model.psystem if model.category == 'detection' else 0
    # sub_system = model.sub_system if model.category == 'detection' else 0

    predict_task_provider(algorithm.name, model.category, model.save_path, model.mid, model.version,
                          model.yname, sub_system, int(params['window']), opt_use, g.unit)

    Model.update_model(mid, version, {'status': ModelStatus.RUNNING})
    Model_timer.update_timer(mid, version, {'export_start': int(time.time())})

    return true_return(msg='success')


def predict_task_provider(model_alg, model_category, model_path, model_mid, model_version, yname, sub_system, window,
                          opt_use, unit):
    pred_msg = {
        "mid": model_mid,
        "unit": unit,
        "version": model_version,
        "opt_use": opt_use
    }
    redis.redis_client.xadd("msg_queue", {"predict": json.dumps(pred_msg)})
    return


@model_blueprint.route('/realtime_eval', methods=['PUT'])
def modify_warning_gate():
    success, data = get_request_data(request, ['mid', 'version', 'warning_gate'])
    if not success:
        return false_return(data)

    mid = data['mid']
    version = data['version']
    model = Model.get_by_id_and_version(mid, version, g.unit)
    if not model:
        return false_return('找不到模型')

    warning_gate = data['warning_gate']
    if warning_gate != model.warning_gate:
        Model.update_model(mid, version, {'warning_gate': warning_gate})

    return true_return('warning_gate修改成功')
