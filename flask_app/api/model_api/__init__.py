import logging
from functools import wraps

from flask import Blueprint, g, request
from flask_app import _get_config
from flask_app.common.before_request import get_request_data, check_unit
from flask_app.common.result import false_return
from flask_app.models.model import Model

model_blueprint = Blueprint('model', __name__, url_prefix='/model')

# logger = logging.getLogger('model')
# logger.setLevel(level=logging.DEBUG if _get_config.DEBUG else logging.INFO)


@model_blueprint.before_request
def before_request():
    success, msg = check_unit()
    if not success:
        return false_return(msg)
    if request.method == 'GET' or request.method == 'DELETE':
        g.data = request.args
        return 
    if request.content_type == 'application/json':
        g.data = request.get_json()


def check_model_and_args(required: list = None, list_fields: list = None):
    def _decorator(func):
        @wraps(func)
        def wrapped_function(*args, **kwargs):
            required_fields = ['mid', 'version']
            if required:
                required_fields.extend(required)
            
            success, data = get_request_data(request, required_fields, list_fields)
            if not success:
                return false_return(data)
            
            target_model = Model.get_by_id_and_version(int(data['mid']), int(data['version']), g.unit)
            if not target_model:
                return false_return('找不到指定模型')
            
            g.model, g.data = target_model, data
            return func(*args, **kwargs)
        return wrapped_function
    return _decorator


def update_model_info(model_path: str, update_data: dict):
    '''
    修改模型model_info.pkl中的信息
    '''
    import os.path as osp
    import pickle

    with open(osp.join(model_path, 'model_info.pkl'), 'rb') as f:
        info = pickle.load(f)
    
    info.update(update_data)

    with open(osp.join(model_path, 'model_info.pkl'), 'wb') as f:
        pickle.dump(info, f)


def find_features_existed(model_features: set, dataset_points: set) -> list:
    features_exists = model_features & dataset_points
    features_non_exists = model_features - features_exists
    assert len(features_exists) > 0, '数据集中没有可用的特征'
    logger.info('使用 {} 进行模型训练. {} 特征在数据集中找不到'.format(features_exists, features_non_exists))
    features = list(features_exists)
    return features


# from .auto_run import add_auto_model
from .lifetime import *
from .model_crud import *
from .realtime import *
