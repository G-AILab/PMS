import json
import multiprocessing
import os
import random
import time
import traceback
import uuid
import mock
import numpy as np
import pandas as pd
from torch import device

import torch.multiprocessing as tmp
from flask import current_app, g, request
from flask_app import _get_config, db, flask_app, new_model_training_pool
from flask_app.api import handle_error
from flask_app.api.model_api.model_crud import check_point_name_in_redis
from flask_app.common.before_request import get_request_data
from flask_app.common.constants import ModelStatus
from flask_app.common.get_scores import get_selected_features
from flask_app.common.result import false_return, true_return
from flask_app.common.send_websocket_msg import send_websocket_msg
from flask_app.models.algorithm import Algorithm
from flask_app.models.dataset import Dataset
from flask_app.models.model import Model
from flask_app.models.model_timer import Model_timer
from flask_app.models.origin_point_dec import OriginPointDesc
from flask_app.models.system_config import SystemConfig
from flask_app.util.common.file_os import allowed_upload, del_file
from flask_app.util.file_util import get_file_encoding, store_request_file
from flask_app.util.log import LoggerPool
from flask_app.util.token_auth import auth
# from flask_app.util.common.file_os import allowed_upload_csv
# from hd.operate import feature_select, optimize
# from hd.operate import train as model_train

from loguru import logger

from . import find_features_existed, model_blueprint


def check_auto_run(model: Model, skip_selection: bool) -> bool:
    """
    检查模型是否包含所有参数
    """
    err_msg = list()
    success = True

    if skip_selection and not model.selected_features:
        success = False
        err_msg.append('要跳过特征选择，必须先设定特征')

    if not model.dataset:
        success = False
        err_msg.append('未设定数据集')
    if not model.train_method:
        success = False
        err_msg.append('未设定训练算法')

    if model.category == 'detection':
        if not model.sub_system:
            success = False
            err_msg.append('未设定目标系统')
    else:
        if not model.yname:
            success = False
            err_msg.append('未设定目标点名')
        if not model.select_method:
            success = False
            err_msg.append('未设定特征选择算法')
    
    return success, err_msg
    # if (model.train is not None) and (model.sub_system is not None) and (model.category == 'detection'):
    #     return True
    # if (model.dataset is None) or (model.select_method is None) or (model.train_method is None) or (model.optimize_method is None):
    #     return False
    # return True




@model_blueprint.route('/auto_run', methods=['POST'])
def add_auto_model():
    from flask_app.util.process_manager import (optimize_processes,
                                                optimizing_processes,
                                                select_processes,
                                                select_wait_processes,
                                                train_processes,
                                                training_processes)
    
    success, data = get_request_data(request, ['mid', 'version'])
    if not success:
        return false_return(data)

    mid = int(data['mid'])
    version = int(data['version'])
    model = Model.get_by_id_and_version(mid=mid, version=version, unit=g.unit)

    if not model:
        return false_return('找不到指定模型')
    
    skip_selection = g.data.get('skip_selection', False)
    skip_opt = g.data.get('skip_opt', False)

    check_suc, check_msg = check_auto_run(model, skip_selection)
    if not check_suc:
        return false_return(check_msg)
    
    select_num = g.data.get('select_num', 20)
    opt_calls = g.data.get('n_calls', 5)
    
    # ctx = tmp.get_context('spawn')
    db.get_engine(app=current_app).dispose()
    p = multiprocessing.Process(target=auto_run_api, args=(model, select_num, opt_calls, g.unit,
                                                           skip_selection, skip_opt,
                                                           optimize_processes, optimizing_processes, 
                                                           select_wait_processes, select_processes, 
                                                           train_processes, training_processes))
    # auto_waiting_processes.append(p.pid)
    p.start()
    return true_return('成功开始自动训练')

autorun_logger = LoggerPool().get()
def mock_auto_run_api(model: Model, select_num: int, n_calls: int, unit: int, skip_selection: bool, skip_opt: bool,
                 optimize_processes, optimizing_processes, select_wait_processes, select_processes, 
                 train_processes, training_processes) -> None:
    autorun_logger.info("start traning", extra={
        "start method": multiprocessing.get_start_method(),
        "context": multiprocessing.get_context(),
        "model":model,
    })
    # from hd.models.regression.xgboost import XGBoost as  regression_XGBoost

    model_path = './test_xgboost_model.pkl'
    data = pd.DataFrame({'N1':np.arange(0,101), 'N2':np.arange(0,101), 'N3':np.arange(0,101)})
    yname='N1'
    sample_step=10
    model = regression_XGBoost(window=30, horizon=10, model_path=model_path, data=data, yname=yname,sample_step=sample_step, max_iter=1, device='cuda:3')
    model.preprocess()
    model.split()
    model.train()
    autorun_logger.info("finish training", extra={
        "model": model,
    })

def auto_run_api(model: Model, select_num: int, n_calls: int, unit: int, skip_selection: bool, skip_opt: bool,
                 optimize_processes, optimizing_processes, select_wait_processes, select_processes, 
                 train_processes, training_processes) -> None:
    try:
        pid = os.getpid()
        assert pid is not None, 'pid is None'
        # while len(training_processes) >= _get_config.MAX_TRANING_MODELS:
        #     time.sleep(5)
        # if pid in waiting_process:
        #     waiting_process.remove(pid)
        # runing_process.append(pid)
        dataset = Dataset.get_by_id(did=model.dataset)
        if not dataset:
            raise AttributeError('找不到数据集')
        
        """
        特征选择
        """
        if model.category != 'detection' and not skip_selection:
            select_algorithm = Algorithm.get_by_id(aid=model.select_method)
            if not select_algorithm:
                raise AttributeError('找不到特征选择算法')
            if model.selection is None:
                model.selection = select_algorithm.defaults
                Model.update_model(model.mid, model.version, {'selection': select_algorithm.defaults})

            select_wait_processes[(model.mid, model.version)] = pid
            while len(select_processes) >= _get_config.MAX_SELECTING_MODELS:
                time.sleep(4 + random.random() * 2)
            select_processes[(model.mid, model.version)] = pid
            select_wait_processes.pop((model.mid, model.version))
            
            model.status = ModelStatus.SELECTING
            update_model_status(model.mid, model.version, ModelStatus.SELECTING)
            Model_timer.update_timer(model.mid, model.version, {'select_start': int(time.time())})
            print(f'M{model.mid}v{model.version} 开始特征选择')
            feature_select(method_name=select_algorithm.name,
                           model_category=model.category,
                           model_path=model.save_path,
                           dataset_path=dataset.path,
                           yname=model.yname,
                           params=json.loads(model.selection))
            print(f'M{model.mid}v{model.version} 特征选择结束')

            score_path = os.path.join(model.save_path, 'selection', 'scores.pkl')
            selected_features = get_selected_features(score_path, select_num)
            # 若模型已存在被选择的特征，说明用户已手动添加了特征
            # 因此取两者的并集
            if model.selected_features:
                features_existed = eval(model.selected_features)
                selected_features = list(set(selected_features) | set(features_existed))
            # selected_features = selected_features[:select_num]
            # Model.update_model(model.mid, model.version, {'selected_features': str(selected_features), 'status': 4})
            Model.update_model(model.mid, model.version, {'selected_features': str(selected_features)})

            Model_timer.update_timer(model.mid, model.version, {'select_end': int(time.time())})
            send_websocket_msg('selection', get_websocket_data(model.mid, model.version, '成功'), room=str(unit), broadcast=False)
            if (model.mid, model.version) in select_processes:
                select_processes.pop((model.mid, model.version))
        elif skip_selection:
            # 跳过特征选择时，创建默认的空日志文件
            log_dir = os.path.join(model.save_path, 'logs')
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            log_file_path = [os.path.join(log_dir, 'selection.log'), os.path.join(log_dir, 'selection_err.log')]
            for log_file in log_file_path:
                if not os.path.exists(log_file):
                    with open(log_file, 'w', encoding='utf-8') as f:
                        f.write('特征选择被跳过')
            if model.category != 'detection':
                selected_features = json.loads(model.selected_features.replace("'", '"'))
        
        model.status = ModelStatus.SELECTING_DONE
        update_model_status(model.mid, model.version, ModelStatus.SELECTING_DONE)
        """
        特征获取完成
        """
        
        """
        训练
        """
        train_algorithm = Algorithm.get_by_id(aid=model.train_method)
        if not train_algorithm:
            raise AttributeError('找不到训练算法')
        update_data = dict()
        if model.train is None:
            model.train = train_algorithm.defaults
            update_data['train'] = train_algorithm.defaults
        if model.general is None:
            model.general = Algorithm.get_general_params(model.category)
            update_data['general'] = model.general
        if update_data:
            Model.update_model(model.mid, model.version, update_data)
        
        train_processes[(model.mid, model.version)] = pid
        model.status = ModelStatus.TRAINING_WAIT
        update_model_status(model.mid, model.version, ModelStatus.TRAINING_WAIT)

        while len(training_processes) >= _get_config.MAX_TRANING_MODELS:
            time.sleep(4 + random.random() * 2)
        training_processes[(model.mid, model.version)] = pid

        if (model.mid, model.version) in train_processes:
            train_processes.pop((model.mid, model.version))

        model.status = ModelStatus.TRAINING
        update_model_status(model.mid, model.version, ModelStatus.TRAINING)
        Model_timer.update_timer(model.mid, model.version, {'train_start': int(time.time())})
        
        params = json.loads(model.general)
        params['train_params'] = json.loads(model.train)

        try:
            dataset_points = set(json.loads(dataset.all_points))
        except:
            logger.info('数据集{} all_points加载失败，跳过相关判断'.format(dataset.did))
            dataset_points = None
        if model.category == "detection":
            # features = SubSystem.get_by_id(model.sub_system)
            # features = features.member
            target_point_config = SystemConfig.get_by_id(model.psystem, unit)
            features = [p.tag_name for p in target_point_config.origin_points]

            if dataset_points:
                features = find_features_existed(set(features), dataset_points)

            # if train_algorithm.name == 'USAD':
            #     params.update({
            #         'w_size': len(features) * params['window'],
            #         'z_size': int(len(features) // 2)
            #     })
            model_train(model_name=train_algorithm.name,
                        category=train_algorithm.category,
                        model_path=model.save_path,
                        dataset_path=dataset.path,
                        sample_step=dataset.sample_step,
                        selected_features=features,
                        yname=model.yname,
                        params=params)
        else:
            if dataset_points:
                selected_features = find_features_existed(set(selected_features), dataset_points)

            model_train(model_name=train_algorithm.name,
                        category=train_algorithm.category,
                        model_path=model.save_path,
                        dataset_path=dataset.path,
                        sample_step=dataset.sample_step,
                        selected_features=selected_features,
                        yname=model.yname,
                        params=params)
        model.status = ModelStatus.TRAINING_DONE
        update_model_status(model.mid, model.version, ModelStatus.TRAINING_DONE)
        
        send_websocket_msg('train', get_websocket_data(model.mid, model.version, '成功'), room=str(unit), broadcast=False)
        Model_timer.update_timer(model.mid, model.version, {'train_end': int(time.time())})
        if (model.mid, model.version) in training_processes:
            training_processes.pop((model.mid, model.version))
        """
        训练结束
        """

        """
        调优
        """
        if model.category != 'detection' and model.optimize_method is not None and not skip_opt:
            model.status = ModelStatus.OPTIMIZING_WAIT
            
            optimize_algorithm = Algorithm.get_by_id(aid=model.optimize_method)
            if not optimize_algorithm:
                raise AttributeError('找不到调优算法')
            
            if not model.optimization:
                model.optimization = optimize_algorithm.defaults
                Model.update_model(model.mid, model.version, {'optimization': optimize_algorithm.defaults})
            
            # add by lc on 5.7; move by wjn on 8.22
            params['train_params'] = json.loads(model.optimization)

            optimize_processes[(model.mid, model.version)] = pid
            update_model_status(model.mid, model.version, ModelStatus.OPTIMIZING_WAIT)

            while len(optimizing_processes) >= _get_config.MAX_TRANING_MODELS:
                time.sleep(4 + random.random() * 2)
            optimizing_processes[(model.mid, model.version)] = pid

            if (model.mid, model.version) in optimize_processes:
                optimize_processes.pop((model.mid, model.version))

            model.status = ModelStatus.OPTIMIZING
            update_model_status(model.mid, model.version, ModelStatus.OPTIMIZING)
            Model_timer.update_timer(model.mid, model.version, {'optimize_start': int(time.time())})

            bp = optimize(model_name=train_algorithm.name,
                        dataset_path=dataset.path,
                        selected_features=selected_features,
                        yname=model.yname,
                        algo=optimize_algorithm.name,
                        category=model.category,
                        params=params,
                        n_calls=n_calls,
                        model_path=model.save_path)
            
            # model.status = ModelStatus.OPTIMIZING_DONE
            # update_model_status(model.mid, model.version, ModelStatus.OPTIMIZING_DONE)
            Model_timer.update_timer(model.mid, model.version, {'optimize_end': int(time.time())})
            data = get_websocket_data(model.mid, model.version, '成功')
            data['best_params'] = str(bp)
            send_websocket_msg('optimize', data, room=str(unit), broadcast=False)
            if (model.mid, model.version) in optimizing_processes:
                optimizing_processes.pop((model.mid, model.version))
        else:
            Model_timer.update_timer(model.mid, model.version, {'optimize_start': int(time.time()), 'optimize_end': int(time.time())})
        model.status = ModelStatus.OPTIMIZING_DONE
        update_model_status(model.mid, model.version, ModelStatus.OPTIMIZING_DONE)
        """
        调优完成
        """
        # send_websocket_msg('auto_run', get_websocket_data(model.mid, model.version, '成功'), broadcast=False, room=str(unit))
        # if pid in runing_process:
        #     runing_process.remove(pid)
    except Exception as e:
        traceback.print_exc()
        if model.status <= 2:
            update_model_status(model.mid, model.version, 2)
            send_websocket_msg('selection', get_websocket_data(model.mid, model.version, '失败', e), broadcast=False, room=str(unit))
        if (model.status <= 5):
            update_model_status(model.mid, model.version, 5)
            send_websocket_msg('selection', get_websocket_data(model.mid, model.version, '失败', e), broadcast=False, room=str(unit))
        elif (model.status <= 9):
            update_model_status(model.mid, model.version, 9)
            send_websocket_msg('train', get_websocket_data(model.mid, model.version, '失败', e), broadcast=False, room=str(unit))
        elif (model.status <= 13):
            update_model_status(model.mid, model.version, 13)
            send_websocket_msg('optimize', get_websocket_data(model.mid, model.version, '失败', e), broadcast=False, room=str(unit))
        else:
            update_model_status(model.mid, model.version, 14)
            send_websocket_msg('auto_run', get_websocket_data(model.mid, model.version, '失败', e), broadcast=False, room=str(unit))
        
        # if pid in runing_process:
        #     runing_process.remove(pid)
        for p in (select_processes, train_processes, training_processes, optimize_processes, optimizing_processes):
            if (model.mid, model.version) in p:
                p.pop((model.mid, model.version))


def get_websocket_data(mid: int, version: int, status: str, exception=None) -> dict:
    data = {
        "mid": mid,
        "version": version,
        "status": status
    }
    if exception:
        data['exception'] = str(exception)
    
    return data


def update_model_status(mid: int, version: int, status: dict) -> None:
    Model.update_model(mid, version, {'status': status})
@model_blueprint.route('/import_models', methods=['POST'])
@auth.login_required
@handle_error
def import_model_from_file():
    
    models_file = request.files['upload_file']
    if not models_file:
        return false_return("需要传入文件")
    
    success = True
    path = None
    try:
        # _, filename, extension = allowed_upload(models_file.filename)
        filename = models_file.filename
        try:
            extension = filename.rsplit('.', 1)[1]
        except IndexError:
            extension = ""
            return false_return('无法解析后缀名!')
        if extension != 'xlsx':
            return false_return('需要上传xlsx文件!')
        filename = str(uuid.uuid3(uuid.NAMESPACE_URL, filename))
        path = os.path.join(flask_app.root_path, _get_config().UPLOAD_FOLDER, filename + '.' + extension)
        models_file.save(path)
        success, msg = create_models_from_file(path)
    except UnicodeDecodeError:
        success = False
        msg = '文件编码错误,无法解析,文件编码格式应为UTF-8 或 GBK 或 GB2312'
    finally:
        if path is not None:
            del_file(path)
    if not success:
        return false_return('文件解析出错', data=msg)
    return true_return("模型批量导入成功")


def create_models_from_file(file_path):
    import numpy as np
    import pandas as pd
    content: pd.DataFrame = pd.read_excel(file_path)
    error_list = list()
    new_models = list()
    runtime_params = list()

    def create_error_str(dataframe_index, msg):
        return '第{}行: {}'.format(dataframe_index + 1, msg)
    
    def is_empty(item):
        if isinstance(item, str):
            return len(item) == 0
        return np.isnan(item)

    category_map = {
        '实时预测': 'prediction',
        '回归分析': 'regression',
        '异常检测': 'detection'
    }

    for index, row in content.iterrows():
        row_error = list()
        
        dataset_name = row['数据集名称']
        target_dataset = None
        if is_empty(dataset_name):
            row_error.append('数据集名称不能为空')
        else:
            target_datasets, _ = Dataset.get_by_name(dataset_name, 0, 1)
            if not target_datasets:
                row_error.append('找不到数据集 {}'.format(dataset_name))
            else:
                target_dataset = target_datasets[0]
        
        category = row['模型类型']
        status = 0
        detection_system = None
        if category not in category_map:
            row_error.append('模型类型只能为 "实时预测", "回归分析", "异常检测"')
        else:
            category = category_map[category]
            if category == 'detection':
                status = 4
                system_name = row['异常检测目标系统']
                if not system_name:
                    row_error.append('异常检测目标不能为空!')
                else:
                    detection_system = SystemConfig.get_by_alias(system_name, g.unit)
                    if not detection_system:
                        row_error.append('找不到目标系统 {}'.format(system_name))
                    elif detection_system.children:
                        row_error.append('不支持对上级系统 {} 建模'.format(system_name))
        
        yname = row['目标点']
        target_point = None
        if category != 'detection':
            if is_empty(yname):
                row_error.append('目标点不能为空')
            else:
                target_point: OriginPointDesc = OriginPointDesc.get_by_name(yname, g.unit)
                if not target_point:
                    row_error.append('数据库点名列表中找不到目标点 {}'.format(yname))
        yname = '' if is_empty(yname) else yname
        
        model_name = row['模型名称']
        if is_empty(model_name) and target_point:
            model_name = target_point.describe

        select_features = row['手动输入特征']
        if not is_empty(select_features):
            select_features = select_features.replace('，', ',').split(',')
            success, err_msg = check_point_name_in_redis(select_features)
            if not success:
                row_error.append(err_msg)
        else:
            select_features = ''
        
        select_alg_name = row['特征选择算法']
        select_num = row['特征选择个数']
        select_alg = None
        if category == 'detection':
            pass
        elif is_empty(select_alg_name):
            row_error.append('请选择特征选择算法')
        elif select_alg_name == '不进行特征选择':
            if not select_features:
                row_error.append('不进行特征选择时必须手动输入特征!')
        else:
            if is_empty(select_num):
                row_error.append('若要进行特征选择，特征选择个数不能为空')
            else:
                select_num = int(select_num)
                if select_num < 0:
                    # 此处select_num表示在手动选择特征之外还需要选择几个特征(因此可以为0)
                    # 最后会将模型选择的特征与手动特征合并作为最终结果
                    row_error.append('特征选择个数必须为非负整数!')
            select_alg = Algorithm.get_by_fuzz_chinese_name(select_alg_name)
            if select_alg is None:
                raise ValueError('未找到该特征选择算法')
        
        train_alg_name = row['训练算法']
        train_alg = None
        if is_empty(train_alg_name):
            row_error.append('训练算法不能为空')
        else:
            train_alg: Model = Algorithm.get_by_chinese_name(train_alg_name)
            if train_alg is None:
                row_error.append('找不到训练算法 "{}"'.format(train_alg_name))

        try:
            general_params = json.loads(Algorithm.get_general_params(category, train_alg.name)) if train_alg else None
        except KeyError:
            general_params = None
        except Exception:
            traceback.print_exc()
        
        window = row['输入时间长度']
        if is_empty(window):
            row_error.append('输入时间长度不能为空')
        else:
            window = int(window)
        
        horizon = row['预测时间长度']
        if is_empty(horizon) and category == 'prediction':
            row_error.append('实时预测模型预测时间长度不能为空')
        else:
            horizon = int(horizon) if not is_empty(horizon) else None
        
        device = row['训练设备']
        if is_empty(device):
            device = 'cuda:0'
        else:
            if not (device.startswith('cuda') or device == 'cpu'):
                row_error.append('无法识别的训练设备')
        
        if general_params is not None:
            general_params['window'] = window
            if category == 'prediction':
                general_params['horizon'] = horizon
            general_params['device'] = device
        
        opt_alg_name = row['调优算法']
        opt_alg = None
        if category == 'detection':
            pass
        elif is_empty(opt_alg_name):
            row_error.append('请选择调优算法')
        elif opt_alg_name != '不进行调优':
            opt_alg = Algorithm.get_by_chinese_name(opt_alg_name)
        
        opt_calls = row['调优次数']
        if opt_alg and is_empty(opt_calls):
            row_error.append('选择调优算法后，调优次数不能为空')
        elif opt_calls:
            opt_calls = int(opt_calls) if not is_empty(opt_calls) else None

        if len(row_error) > 0:
            error_list.append(create_error_str(index, '; '.join(row_error)))
            # error_list.extend(row_error)
        else:
            new_models.append({
                'name': model_name,
                'category': category,
                'status': status,
                'yname': yname,
                'dataset': target_dataset.did if target_dataset else None,
                'train_method': train_alg.aid if train_alg else None,
                'train': train_alg.defaults if train_alg else None,
                'select_method': select_alg.aid if select_alg else None,
                'optimize_method': opt_alg.aid if opt_alg else None,
                'auto_run': 1,
                'general': json.dumps(general_params),
                'psystem': detection_system.cid if detection_system else None,
                'create_user': g.user.uid,
                'unit': int(g.unit),
                'selected_features': str(select_features)
            })

            runtime_params.append({
                'select_num': select_num,
                'n_calls': opt_calls,
                'skip_selection': select_alg is None,
                'skip_opt': opt_alg is None
            })
    
    if error_list:
        return False, error_list
    
    mids_created = Model.create_models(new_models)
    post_models_autorun(mids_created, runtime_params)
    return True, ''


def post_models_autorun(mids, runtime_params):
    from flask_app.util.process_manager import (optimize_processes,
                                                optimizing_processes,
                                                select_wait_processes,
                                                select_processes,
                                                train_processes,
                                                training_processes,
                                                task_proc_pool,
                                                model_training_pool)
    # model_training_pool = new_model_training_pool()
    for mid, runtime_param in zip(mids, runtime_params):
        model: Model = Model.get_by_id_and_version(mid, 1, g.unit)
        select_num = runtime_param['select_num']
        opt_calls = runtime_param['n_calls']
        skip_selection = runtime_param['skip_selection']
        skip_opt = runtime_param['skip_opt']

        db.get_engine(app=current_app).dispose()
        model_training_pool.schedule(auto_run_api,args=( model, select_num, opt_calls, g.unit,
                                            skip_selection, skip_opt,
                                            optimize_processes, optimizing_processes, 
                                            select_wait_processes, select_processes,
                                            train_processes, training_processes))

