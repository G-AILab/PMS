import time

import os
from flask_app import _get_config
import psutil
from GPUtil import GPUtil
from flask import Blueprint

from flask_app.common.result import true_return

sys_blueprint = Blueprint("sys_blueprint", __name__, url_prefix='/sys')


@sys_blueprint.route('/servers', methods=['GET'])
def get_servers_stat():
    res_dir = _get_config.SERVER_STAT_RES_DIR
    res_files = list(filter(lambda x: x.endswith('.txt'), os.listdir(res_dir)))

    servers_data = list()
    for f in res_files:
        with open(os.path.join(res_dir, f), 'r') as rf:
            lines = rf.read().split('\n')
        res_tuples = [(line.split(': ')[0], eval(line.split(': ')[1])) for line in lines]
        res_dict = dict(res_tuples)
        res_dict['name'] = f.split('_')[0]
        res_dict['gpu'] = sum(res_dict['gpu']) / len(res_dict['gpu']) if len(res_dict['gpu']) > 0 else None
        servers_data.append(res_dict)
    
    return true_return('服务器列表查询成功', servers_data)


@sys_blueprint.route('/memory', methods=['GET'])
def get_memory():
    data = {
        "mem_percent": psutil.virtual_memory().percent
    }
    return true_return("查询内存成功", data)


@sys_blueprint.route('/cpu', methods=['GET'])
def get_cpu():
    data = {
        "cpu_percent": psutil.cpu_percent()
    }
    return true_return("查询CPU成功", data)


@sys_blueprint.route('/gpu', methods=['GET'])
def get_gpu():
    results = get_fixed_gpus()
    
    data = {
        "gpu_cnt": len(results),
        'gpus': results
    }
    return true_return("查询GPU成功", data)


def get_fixed_gpus():
    return [
        {
            'id': 0,
            'name': 'Fixed GPU 0',
        },
    ]


def get_gpu_from_gputil():
    gpus = GPUtil.getGPUs()
    GPUtil.showUtilization()
    results = []
    for gpu in gpus:
        result = {
            'id': gpu.id,
            'name': gpu.name,
            'serial': gpu.serial,
            'uuid': gpu.uuid,
            'load': gpu.load * 100,
            'memoryUtil': gpu.memoryUtil * 100,
            'memoryTotal': gpu.memoryTotal,
            'memoryUsed': gpu.memoryUsed,
            'memoryFree': gpu.memoryFree,
            'display_mode': gpu.display_mode,
            'display_active': gpu.display_active
        }
        results.append(result)

    return results


@sys_blueprint.route('/sleep', methods=['GET'])
def sleep_test():
    print("收到请求")
    time.sleep(300)
    return true_return("没超时")
