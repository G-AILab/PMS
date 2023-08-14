import json
import os
import traceback

import requests
from loguru import logger


def check_processes_task():
    logger.info('Start to check model task processes...')
    plists = query_processes()

    dead_processes = list()
    for pname, plist in plists.items():
        for key, pid in plist.items():
            mid, version = eval(key)
            if not check_process_alive(pid):
                dead_processes.append({
                    "target": pname,
                    "mid": mid,
                    "version": version
                })
    
    if len(dead_processes) > 0:
        logger.warning('开始清理 {} 个已死亡进程...'.format(len(dead_processes)))
    
    apply_processes_modification(dead_processes)


def check_process_alive(pid: int):
    try:
        os.kill(pid, 0)
        return True
    except:
        return False


def query_processes() -> dict:
    url = 'http://localhost:18888/api/model/processes'
    headers = {'unit': '3'}
    params = {'type': 'all'}

    try:
        resp = requests.get(url, params=params, headers=headers)
    except:
        logger.error(traceback.format_exc())
    
    resp = resp.json()
    if not resp['status']:
        logger.warning('查询失败: {}'.format(resp['msg']))
        return
    return resp['data']


def apply_processes_modification(operations: list):
    url = 'http://localhost:18888/api/model/pop_processes'
    headers = {'unit': '3', 'Content-Type': 'application/json'}
    data = {'operation': operations}

    try:
        resp = requests.post(url, data=json.dumps(data), headers=headers)
    except:
        logger.error(traceback.format_exc())
        return
    
    if resp.status_code == 200:
        resp = resp.json()
        if not resp['status']:
            logger.warning('process修改请求失败: {}'.format(resp['msg']))
    else:
        logger.error(resp.text)


if __name__ == "__main__":
    check_processes_task()
