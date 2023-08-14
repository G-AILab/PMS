import json
import os
from time import time

from flask import Blueprint, request
from flask_app import flask_app
from flask_app.common.before_request import get_border, get_request_data
from flask_app.common.result import false_return, true_return
from flask_app.config.default import Config
from flask_app.models.algorithm import Algorithm
from flask_app.util.common.file_os import allowed_upload
from flask_app.api import handle_error

algorithm_blueprint = Blueprint("algorithm_blueprint", __name__, url_prefix='/algorithm')


@algorithm_blueprint.route('/param_desc', methods=['GET'])
@handle_error
def get_alorithm_param_describe():
    success, data = get_request_data(request, ['aid'])
    if not success:
        return false_return(data)
    
    aid = data['aid']
    alg = Algorithm.get_by_id(aid)
    if not alg:
        return false_return('找不到指定算法')

    try:
        names = json.loads(alg.parameters)
        default_values = json.loads(alg.defaults)
        param_descs = json.loads(alg.param_desc)
    except Exception as e:
        print(e)
        return false_return('读取参数详情失败')
    
    res = list()
    for en_names, cn_names in names.items():
        if en_names in default_values and en_names in param_descs:
            res.append({
                'name': en_names,
                'chinese_name': cn_names,
                'describe': param_descs[en_names],
                'default_value': default_values[en_names]
            })
    
    return true_return('参数详情获取成功', res)


@algorithm_blueprint.route('', methods=['GET'])
@handle_error
def get_algorithm():
    have_aid, data = get_request_data(request, ['aid'])
    if not have_aid:
        have_page, left, right = get_border(request)
        if have_page:
            algorithms, total = Algorithm.get_by_page(left, right)
        else:
            algorithms, total = Algorithm.get_all()
        result = {
            'total': total,
            'algorithms': [algorithm.to_json() for algorithm in algorithms]
        }
        return true_return("查询成功", result)
    aid = data['aid']
    algorithm = Algorithm.get_by_id(aid)
    return true_return("查询成功", algorithm.to_json())


@algorithm_blueprint.route('', methods=['POST'])
@handle_error
def create_algorithm():
    success, data = get_request_data(request, ['name', 'category', 'type', 'parameters', 'defaults'])
    if not success:
        return false_return(data)
    name = data['name']
    category = data['category']
    atype = data['type']
    parameters = data['parameters']
    defaults = data['defaults']
    algorithm = Algorithm.create(name, category, atype, parameters, defaults)
    return true_return("创建成功", algorithm.to_json())


@algorithm_blueprint.route('', methods=['PUT'])
@handle_error
def update_algorithm():
    success, data = get_request_data(request, ['aid'])
    if not success:
        return false_return(data)
    aid = data['aid']
    algorithm = Algorithm.get_by_id(aid)
    if not algorithm:
        return false_return("算法不存在")
    try:
        name = data['name']
    except KeyError:
        name = algorithm.name
    try:
        category = data['category']
    except KeyError:
        category = algorithm.category
    try:
        atype = data['type']
    except KeyError:
        atype = algorithm.atype
    try:
        parameters = data['parameters']
    except KeyError:
        parameters = algorithm.parameters
    try:
        defaults = data['defaults']
    except KeyError:
        defaults = algorithm.defaults
    try:
        chinese_name = data['chinese_name']
    except KeyError:
        chinese_name = algorithm.chinese_name
    try:
        description = data['description']
    except KeyError:
        description = algorithm.description
    algorithm = Algorithm.update_algorithm(aid, name, category, atype, parameters, defaults, chinese_name, description)
    return true_return("修改成功", algorithm.to_json())


@algorithm_blueprint.route('', methods=['DELETE'])
@handle_error
def delete_algorithm():
    success, data = get_request_data(request, ['aid'])
    if not success:
        return false_return(data)
    aid = data['aid']
    algorithm = Algorithm.get_by_id(aid)
    if not algorithm:
        return false_return("算法不存在")
    Algorithm.delete_algorithm(aid)
    return true_return("删除成功", algorithm.to_json())


@algorithm_blueprint.route('/statistic', methods=['GET'])
def statistic():
    statistics = Algorithm.statistic()
    return true_return("统计成功", statistics)


@algorithm_blueprint.route('/upload_file', methods=['POST'])
@handle_error
def upload_file():
    success, data = get_request_data(request, ['aid'])
    if not success:
        return false_return(data)
    aid = data['aid']
    algorithm_file = request.files['algorithm_file']
    algorithm = Algorithm.get_by_id(aid)
    if not algorithm:
        return false_return("算法不存在")
    if algorithm_file:
        allowed, filename, extension = allowed_upload(algorithm_file.filename)
        if not allowed:
            error_message = "文件后缀名必须是" + str(Config.ALLOWED_EXTENSIONS) + '中的一种'
            return false_return(error_message)
        now = int(time())
        save_filename = '_algorithm_' + aid + '_file_' + str(now) + "." + extension
        algorithm_file.save(os.path.join(flask_app.root_path, Config.UPLOAD_FOLDER, save_filename))
        file_path = Config.FLASK_URL + Config.UPLOAD_FOLDER + save_filename
        algorithm.update_file(aid, file_path)
        return true_return("文件上传成功")
    return false_return("请选择文件")


@algorithm_blueprint.route('/filter_by_type', methods=['GET'])
@handle_error
def filter_by_type():
    success, data = get_request_data(request, ['category', 'atype'])
    if not success:
        return false_return(data)
    category = data['category']
    atype = data['atype']
    algorithms = Algorithm.filter_by_type(category, atype)
    data = [algorithm.to_json() for algorithm in algorithms]
    return true_return('按类型查询成功', data)


@algorithm_blueprint.route('/get_paras', methods=['GET'])
@handle_error
def get_paras():
    success, data = get_request_data(request, ['aid'])
    if not success:
        return false_return(data)
    aid = data['aid']
    success, result = Algorithm.get_paras(aid)
    if not success:
        return false_return('算法中出现无法解析的非法字段！')
    return true_return('查询成功', result)


@algorithm_blueprint.route('/search', methods=['GET'])
@handle_error
def search_name():
    success, data = get_request_data(request, ['name'])
    if not success:
        return false_return(data)
    name = data['name']
    searched_algorithms = Algorithm.search_name(name)
    result = [algorithm.to_json() for algorithm in searched_algorithms]
    return true_return('搜索成功', result)
