from flask import Blueprint, request, g, session,current_app
import traceback
import json
import redis
import math
import arrow
import chardet
import pyarrow.parquet as pq
import pyarrow as pa
from flask_app.common.before_request import get_request_data, get_border, check_unit
from flask_app.common.result import false_return, true_return
from flask_app.api import handle_error
from flask_app.models.dataset import Dataset
from flask_app.models.origin_point_dec import OriginPointDesc
from flask_app.models.indicator import Indicator
from flask_app import influx, db, redis as red
from flask_app.util.common.time_trans import *
from flask_app.util.common.file_os import *
from flask_socketio import emit
import multiprocessing
from flask_app.common.send_websocket_msg import send_websocket_msg
from flask_app.util.token_auth import auth
from flask_app.config.default import Config
from  loguru  import logger
import signal
from pandas import read_parquet
from datetime import datetime as DT
import numpy as np

ip = Config.REDIS_HOST
port = Config.REDIS_PORT
REDIS_EXPIRE_TIME = 120  # 插入的数据的过期时间

r = redis.Redis(host=ip, port=port, db=2, decode_responses=True)

dataset_blueprint = Blueprint('dataset', __name__, url_prefix='/dataset')

@dataset_blueprint.before_request
@handle_error
def before_request():
    if request.method == 'GET' or request.method == 'DELETE':
        g.data = request.args
    else:
        content_type = request.headers.get('Content-Type')
        if (content_type == 'application/json'):
            g.data = request.get_json()


@dataset_blueprint.route('', methods=['GET'])
@handle_error
def get_dataset():
    have_did, data = get_request_data(request, ['did'])
    dataset_name = g.data.get('name')
    need_keys = None
    if 'fields' in g.data:
        try:
            need_keys = g.data['fields'].strip().split(',')
        except:
            return false_return('"fields"解析失败')
    if not have_did:
        have_page, left, right = get_border(request)
        if have_page:
            if dataset_name:
                datasets, total = Dataset.get_by_name(dataset_name, left, right)
            else:
                datasets, total = Dataset.get_by_page(left, right)
        else:
            if dataset_name:
                datasets, total = Dataset.search_all(dataset_name)
            else:
                datasets, total = Dataset.get_all()
        if need_keys:
            result = {
                'total': total,
                'datasets': [{k: v for k, v in dataset.to_json().items() if k in need_keys} for dataset in datasets],
            }
        else:
            result = {
                'total': total,
                'datasets': [dataset.to_json() for dataset in datasets],
            }
        return true_return("查询成功", result)
    did = data['did']
    dataset = Dataset.get_by_id(did)
    if dataset:
        if need_keys:
            return true_return("查询成功", {k: v for k, v in dataset.to_json().items() if k in need_keys})
        else:
            return true_return("查询成功", dataset.to_json())
    else:
        return false_return("查询失败,不存在该数据集")

def get_encoding(file):
    with open(file,'rb') as f:
        tmp = chardet.detect(f.read())
        return tmp['encoding']

def string_encoding(data: bytes):
    """
    获取字符编码类型
    :param data: 字节数据
    :return:
    """
    UTF_8_BOM = b'\xef\xbb\xbf'
    CODES = ['UTF-8', 'GB18030', 'BIG5']
    # 遍历编码类型
    for code in CODES:
        try:
            data.decode(encoding=code)
            if 'UTF-8' == code and data.startswith(UTF_8_BOM):
                return 'UTF-8-SIG'
            return code
        except UnicodeDecodeError:
            continue
    return 'unknown'

@dataset_blueprint.route('/upload_file', methods=['POST'])
@auth.login_required
@handle_error
def upload_file():
    try:
        tags_file = request.files['tags_file']
        if tags_file:
            allowed, filename, extension = allowed_upload_csv(tags_file.filename)
            if not allowed:
                error_message = "文件后缀名必须是.csv"
                return false_return(msg=error_message)
            
            file = chardet.detect(tags_file.read())
            format = file['encoding']
            tags_file.seek(0)
            data = pd.read_csv(tags_file, encoding=format)
            tags = data['keys'].tolist()
            if len(tags):
                latest = red.read('latest')
                for i, point in enumerate(tags):
                    key = str(latest) + '@' + str(point)
                    key = key.strip()
                    tags[i] = str(point).strip()
                    # print(key, red.read(key))
                    if red.read(key) is None:
                        return false_return(msg="存在未找到的点名:"+point)
                uid = str(g.user.uid)
                r.set('uid_'+uid, ','.join(tags))
                return true_return(msg="文件上传成功")
            else:
                return false_return(msg='上传点名不能为空')
        return false_return(msg="请选择文件")
    except UnicodeDecodeError as e:
        traceback.print_exc()
        return false_return(msg='编码格式错误')
    except Exception as e:
        traceback.print_exc()
        return false_return(msg='csv文件中需要有keys列')

@dataset_blueprint.route('/remove_tags', methods=['GET'])
@auth.login_required
@handle_error
def clear_selected_tags():
    uid = str(g.user.uid)
    if r.get('uid_'+ uid):
        r.delete('uid_'+ uid)
    return true_return(msg='移除点名列表成功')


# @dataset_blueprint.route('', methods=['POST'])
# @auth.login_required
# @handle_error
# def add_new_dataset():
#     from flask_app.util.process_manager import add_dataset_processes
#     sample_step = g.data.get('sample_step')
#     name = g.data.get('name')
#     current = int(time.time())
#     path = '/workspace/data/' + name + '_' + str(current) + '.parquet'
#     start_time = g.data.get('start_time')
#     start_time = Normaltime(start_time)
#     end_time = g.data.get('end_time')
#     end_time = Normaltime(end_time)
#     drop_null = g.data.get('drop_null')
#     drop_null = int(drop_null)
#     drop_unchanging = g.data.get('drop_unchanging')
#     drop_unchanging = int(drop_unchanging)
#     tags = []
#     uid = str(g.user.uid)
#     if r.get('uid_'+ uid):
#         tags_selected = r.get('uid_'+uid).split(',')
#         for tag in tags_selected:
#             tags.append(tag)
#             # print(tag)
#     try:
#         did = Dataset.add(sample_step, path, start_time, end_time, name, status=0, process=0.00)
#         ctx = multiprocessing.get_context('spawn')
#         db.get_engine(app=current_app).dispose()
#         p = ctx.Process(target=add_new_dataset, args=(did, sample_step, name, path, start_time, end_time, tags, add_dataset_processes, drop_null, drop_unchanging))
#         p.start()
#         return true_return(msg="创建成功")
#     except:
#         return false_return(msg="创建失败")

# def add_new_dataset(did, sample_step, name, path, start_time, end_time, selected_tags, processes, drop_null, drop_unchanging):
#     pid = os.getpid()
#     data = {
#         "name": name,
#         "path": path
#     }
#     try:
#         processes[str(did)] = pid
#         pre_check = 0
#         for res in influx.query(sample_step, start_time, end_time, selected_tags, chunked=True, chunk_size=60):
#                 pre_check = len(list(res.get_points()))
#                 break
#         if pre_check:
#             sec = (arrow.get(end_time) - arrow.get(start_time)).total_seconds() + 1
#             chunk_size = 60
#             if sec % sample_step != 0:
#                 sec //= sample_step
#                 sec += 1
#             else:
#                 sec //= sample_step
#             chunk_count = 0

#             results = list()
#             for res in influx.query(sample_step, start_time, end_time, selected_tags, chunked=True, chunk_size=chunk_size):
#                 chunk_count += len(list(res.get_points()))
#                 values = res._raw['series'][0]['values']
#                 results.extend(values)
#                 if chunk_count == 60:
#                     columns = res._raw['series'][0]['columns']
#                 cur_process =  round(chunk_count / sec * 100 , 2)
#                 Dataset.update_info(did, {'process': cur_process})
#             result = pd.DataFrame(results, columns=columns, dtype=np.float32)
#             result = result.fillna(method='ffill')
#             result = result.fillna(method='bfill')
#             result.drop('time', axis = 1, inplace = True)
#             logger.info('数据集填充完成!')
            
#             static_points = []
#             null_points = []
#             all_points = []

#             for col in result.columns:
#                 all_points.append(col)
#                 if result[col].dtype == np.float32:
#                     if math.isclose(result[col].std(), 0, rel_tol=1e-09, abs_tol=0.0):
#                         static_points.append(col)
#                 if result[col].isnull().all():
#                     null_points.append(col)
            
#             if drop_null:
#                 result = result.dropna(axis = 'columns', how = 'all') 
#                 all_points = list(set(all_points) - set(null_points))
#             if drop_unchanging:
#                 result = result.drop(static_points, axis=1)
#                 all_points = list(set(all_points) - set(static_points))
            
#             logger.info(f"{len(static_points)}{len(null_points)}")
#             table = pa.Table.from_pandas(result)
#             pq.write_table(table, path)
            
#             r.set(f'did_{did}', 1)        #设置初始状态码 1: 可以从磁盘读取数据集 0：不能从磁盘读取数据集
            
#             data_size = get_FileSize(path)
#             new_data = {}
#             new_data['null_points'] = json.dumps(null_points)
#             new_data['static_points'] = json.dumps(static_points)
#             new_data['all_points'] = json.dumps(all_points)
#             new_data['status'] = 1
#             new_data['process'] = 100.00
#             new_data['size'] = data_size
#             Dataset.update_info(did, new_data)
#             data['status'] = '成功'
#             data['msg'] = '数据集创建成功!'
#             logger.info(f"{data}")
#             send_websocket_msg('add_dataset', data, broadcast=True, namespace='/websocket')
#         else:
#             data['status'] = '空集'
#             data['msg'] = '该时段没有数据,请重新选择'
#             Dataset.delete(did)
#             logger.info(f"{data}")
#             send_websocket_msg('add_dataset', data, broadcast=True, namespace='/websocket')
#     except Exception as e:
#         data['status'] = '失败'
#         data['msg'] = '数据集创建失败'
#         logger.warning(f"{data}")
#         logger.warning(f"{e}")
#         Dataset.update_info(did, {'status':-1})
#         send_websocket_msg('add_dataset', data, broadcast=True, namespace='/websocket')
#         traceback.print_exc()
#     if str(did) in processes:
#         processes.pop(str(did))
@dataset_blueprint.route('', methods=['POST'])
@auth.login_required
@handle_error
def add_new_dataset():
    from flask_app.util.process_manager import add_dataset_processes
    sample_step = g.data.get('sample_step')
    name = g.data.get('name')
    current = int(time.time())
    path = '/workspace/data/' + name + '_' + str(current) + '.parquet'
    start_time = g.data.get('start_time')
    start_time_lis = [Normaltime(t) for t in start_time]
    end_time = g.data.get('end_time')    
    end_time_lis = [Normaltime(t) for t in end_time]
    drop_null = g.data.get('drop_null')
    drop_null = int(drop_null)
    drop_unchanging = g.data.get('drop_unchanging')
    drop_unchanging = int(drop_unchanging)
    tags = []
    uid = str(g.user.uid)
    if r.get('uid_'+ uid):
        tags_selected = r.get('uid_'+uid).split(',')
        for tag in tags_selected:
            tags.append(tag)
            # print(tag)
    try:
        did = Dataset.add(sample_step, path, start_time_lis[0], end_time_lis[-1], name, status=0, process=0.00)
        ctx = multiprocessing.get_context('spawn')
        db.get_engine(app=current_app).dispose()
        p = ctx.Process(target=add_new_dataset, args=(did, sample_step, name, path, start_time_lis, end_time_lis, tags, add_dataset_processes, drop_null, drop_unchanging))
        p.start()
        return true_return(msg="创建成功")
    except:
        return false_return(msg="创建失败")

def add_new_dataset(did, sample_step, name, path, start_time_lis, end_time_lis, selected_tags, processes, drop_null, drop_unchanging):
    pid = os.getpid()
    data = {
        "name": name,
        "path": path
    }
    try:
        processes[str(did)] = pid
        total_sec = 0
        results = list()
        #验证每段时间段是否都有值
        for start_time, end_time in zip(start_time_lis, end_time_lis):
            pre_check = 0
            for res in influx.query(sample_step, start_time, end_time, selected_tags, chunked=True, chunk_size=100):
                pre_check = len(list(res.get_points()))
                break
            if pre_check == 0:
                data['status'] = '空集'
                data['msg'] = '该时段没有数据,请重新选择'
                Dataset.delete(did)
                logger.info(f"{data}")
                send_websocket_msg('add_dataset', data, broadcast=True, namespace='/websocket')
                return
            else:
                total_sec += (arrow.get(end_time) - arrow.get(start_time)).total_seconds() + 1
        #计算总的chunk数
        chunk_size = 60
        if total_sec % sample_step != 0:
            total_sec //= sample_step
            total_sec += 1
        else:
            total_sec //= sample_step
        chunk_count = 0
        flag = False
        #对每个时间段分开处理
        for start_time, end_time in zip(start_time_lis, end_time_lis):
            for res in influx.query(sample_step, start_time, end_time, selected_tags, chunked=True, chunk_size=chunk_size):
                chunk_count += len(list(res.get_points()))
                values = res._raw['series'][0]['values']
                results.extend(values)
                if chunk_count == chunk_size and flag == False:
                    columns = res._raw['series'][0]['columns']
                    flag = True
                cur_process =  round(chunk_count / total_sec * 100 , 2)
                Dataset.update_info(did, {'process': cur_process})
                # print("process:{:.2f}%".format(chunk_count / sec * 100 - 1))
        result = pd.DataFrame(results, columns=columns)
        result = result.fillna(method='ffill')
        result = result.fillna(method='bfill')
        result.drop('time', axis = 1, inplace = True)
        logger.info('数据集填充完成!')
        
        static_points = list()
        null_points = list()
        all_points = list()

        for col in result.columns:
            all_points.append(col)
            float_col = pd.to_numeric(result[col])
            if math.isclose(float_col.std(), 0, rel_tol=1e-09, abs_tol=0.0):
                static_points.append(col)
            if float_col.isnull().all():
                null_points.append(col)
        
        if drop_null:
            result = result.dropna(axis = 'columns', how = 'all') 
            all_points = list(set(all_points) - set(null_points))
        if drop_unchanging:
            result = result.drop(static_points, axis=1)
            all_points = list(set(all_points) - set(static_points))
        
        logger.info(f"{len(static_points)} {len(null_points)}")
        table = pa.Table.from_pandas(result)
        pq.write_table(table, path)

        r.set(f'did_{did}', 1)        #设置初始状态码 1: 可以从磁盘读取数据集 0：不能从磁盘读取数据集

        data_size = get_FileSize(path)
        new_data = {}
        new_data['null_points'] = json.dumps(null_points)
        new_data['static_points'] = json.dumps(static_points)
        new_data['all_points'] = json.dumps(all_points)
        new_data['status'] = 1
        new_data['process'] = 100.00
        new_data['size'] = data_size
        Dataset.update_info(did, new_data)
        data['status'] = '成功'
        data['msg'] = '数据集创建成功!'
        logger.info(f"{data}")
        send_websocket_msg('add_dataset', data, broadcast=True, namespace='/websocket')
    except Exception as e:
        data['status'] = '失败'
        data['msg'] = '数据集创建失败'
        logger.warning(f"{data}")
        logger.warning(f"{e}")
        Dataset.update_info(did, {'status':-1})
        send_websocket_msg('add_dataset', data, broadcast=True, namespace='/websocket')
        traceback.print_exc()
    if str(did) in processes:
        processes.pop(str(did))

#更新数据集时间长度
@dataset_blueprint.route('', methods=['PUT'])
@handle_error
def update_dataset_info():
    from flask_app.util.process_manager import update_dataset_processes
    success, data = get_request_data(request, ['did','end_time'])
    if not success:
        return false_return(data)
    did = data['did']
    try:
        is_available = r.get(f'did_{did}')
        if is_available is None or int(is_available) == 1:
            r.set(f'did_{did}', 0)      
            new_time = Normaltime(data['end_time'])
            dataset = Dataset.get_by_id(did).to_json()
            old_time = Normaltime(Localtime(dataset["end_time"]))
            old_timestamp = int(Changestamp(old_time))
            new_timestamp = int(Changestamp(new_time))
            if old_timestamp >= new_timestamp:
                return false_return('更新的采样结束时间不能早于之前的采样结束时间!')
            ctx = multiprocessing.get_context('spawn')
            db.get_engine(app=current_app).dispose()
            p = ctx.Process(target=update_dataset, args=(did, new_time, update_dataset_processes))
            p.start()
            return true_return(msg="正在更新数据集")
        else:
            return false_return(msg='该数据集正在被修改,请稍后重试')
    except Exception as e:
        r.set(f'did_{did}', 1)          #更新数据集操作状态
        logger.warning(str(e))
        return false_return("更新数据集失败")


def update_dataset(did, new_time, processes):
    """
        更新数据集长度
        ---------
        Args:
            did: 数据集id
            new_time: 要更新的最新结束时间
            processes: 进程字典
        ----------
        Returns:
        ----------
                """
    try:
        pid = os.getpid()
        processes[did] = pid
        dataset = Dataset.get_by_id(did).to_json()
        data = {
        "name": dataset["name"],
        }
        sample_step = dataset["sample_step"]
        start_time = Normaltime(Localtime(dataset["end_time"]))
        end_time = new_time
        path = dataset["path"]
        all_points = dataset['all_points']
        sec = (arrow.get(end_time) - arrow.get(start_time)).total_seconds() + 1
        if sec % sample_step != 0:
            sec //= sample_step
            sec += 1
        else:
            sec //= sample_step
        chunk_size = 60
        chunk_count = 0
        results = list()
        for res in influx.query(sample_step, start_time, end_time, all_points, chunked=True, chunk_size=chunk_size):
            chunk_count += len(list(res.get_points()))
            values = res._raw['series'][0]['values']
            results.extend(values)
            if chunk_count == 60:
                columns = res._raw['series'][0]['columns']
            cur_process =  round(chunk_count / sec * 100 , 2)
            Dataset.update_info(did, {'update_process': cur_process})
        result = pd.DataFrame(results, columns = columns)
        result = result.fillna(method='ffill')
        result = result.fillna(method='bfill')
        result.drop('time', axis = 1, inplace = True)
        logger.info('更新数据集查询完成!')
        df = read_parquet(path)
        logger.info('加载原始数据集完成!')
        res = df.append(result, ignore_index=True)
        
        table = pa.Table.from_pandas(res)
        pq.write_table(table, path)
        data_size = get_FileSize(path)
        new_data = {}
        new_data['end_time'] = end_time
        new_data['size'] = data_size
        new_data['update_status'] = 1
        new_data['update_process'] = 100.00
        Dataset.update_info(did, new_data)
        
        data['status'] = '成功'
        data['msg'] = '更新数据集成功!'
        logger.info(f"{data}")
    except Exception as e:
        Dataset.update_info(did, {'update_status':2})
        data['status'] = '失败'
        data['msg'] = '更新数据集失败'
        logger.warning(f"{data}")
        logger.warning(f"{e}")
        traceback.print_exc()
    if did in processes:
        processes.pop(did)
    


@dataset_blueprint.route('', methods=['DELETE'])
@handle_error
def delete_dataset():
    from flask_app.util.process_manager import add_dataset_processes
    did = g.data.get('did')
    try:
        is_available = r.get(f'did_{did}')
        if is_available is None or int(is_available) == 1:
            r.set(f'did_{did}', 0)
            if str(did) in add_dataset_processes:
                target_pid = add_dataset_processes[str(did)]
                add_dataset_processes.pop(str(did))
                os.kill(target_pid, signal.SIGKILL)
            dataset = Dataset.get_by_id(did)
            path = dataset.path
            del_file(path)
            Dataset.delete(did)
            return true_return("删除成功")
        else:
            return false_return(msg='该数据集正在被修改,请稍后重试')
    except Exception as e:
        r.set(f'did_{did}', 1)          #更新数据集操作状态
        logger.warning(str(e))
        return false_return("该数据集不存在")

#追加填充数据集
@dataset_blueprint.route('/append_points', methods=['POST'])
@handle_error
def append_new_points():
    from flask_app.util.process_manager import append_points_process
    success, data = get_request_data(request, ['did','points_value'], list_fields=['points_value'])
    if not success:
        return false_return(data)
    points = data['points_value']
    # points = points_value.split(',')
    did = data['did']
    try:
        if len(points):
            is_available = r.get(f'did_{did}')
            if is_available is None or int(is_available) == 1:
                r.set(f'did_{did}', 0)
                latest = red.read('latest')
                for i, point in enumerate(points):
                    points[i] = str(point).strip()
                    key = str(latest) + '@' + str(point)
                    key = key.strip()
                    if red.read(key) is None:
                        return false_return(msg="存在未找到的点名:"+point)
                Dataset.update_info(did, {'append_status':0})
                ctx = multiprocessing.get_context('spawn')
                db.get_engine(app=current_app).dispose()
                p = ctx.Process(target=append_new_points, args=(did, points, append_points_process))
                p.start()
                return true_return(msg="正在追加点名")
            else:
                return false_return(msg='该数据集正在被修改,请稍后重试')
        else:
            return false_return(msg='追加的点名不能为空')
    except Exception as e:
        r.set(f'did_{did}', 1)          #更新数据集操作状态
        logger.warning(str(e))
        return false_return("追加点名失败")

@dataset_blueprint.route('/stop_append', methods=['DELETE'])
@handle_error
def stop_append_points():
    try:
        from flask_app.util.process_manager import append_points_process
        did = g.data.get('did')
        if did in append_points_process:
            logger.info(str(did))
            target_pid = append_points_process[did]
            append_points_process.pop(did)
            os.kill(target_pid, signal.SIGKILL)
        return true_return("停止填充成功")
    except Exception as e:
        logger.warning(str(e))
        return false_return("该数据集不存在")

def append_new_points(did, points, processes):
    """
        向数据集中追加点名
        ---------
        Args:
            did: 数据集id
            points: 要追加的点名列表
            processes: 进程字典
        ----------
        Returns:
        ----------
                """
    try:
        pid = os.getpid()
        processes[did] = pid
        dataset = Dataset.get_by_id(did).to_json()
        data = {
        "name": dataset["name"],
        }
        sample_step = dataset["sample_step"]
        start_time = Normaltime(Localtime(dataset["start_time"]))
        end_time = Normaltime(Localtime(dataset["end_time"]))
        path = dataset["path"]
        sec = (arrow.get(end_time) - arrow.get(start_time)).total_seconds() + 1
        if sec % sample_step != 0:
            sec //= sample_step
            sec += 1
        else:
            sec //= sample_step
        chunk_size = 60
        chunk_count = 0
        results = list()
        for res in influx.query(sample_step, start_time, end_time, points, chunked=True, chunk_size=chunk_size):
            chunk_count += len(list(res.get_points()))
            values = res._raw['series'][0]['values']
            results.extend(values)
            if chunk_count == 60:
                columns = res._raw['series'][0]['columns']
            cur_process =  round(chunk_count / sec * 100 , 2)
            Dataset.update_info(did, {'append_process': cur_process})
        result = pd.DataFrame(results, columns = columns)
        result = result.fillna(method='ffill')
        result = result.fillna(method='bfill')
        result.drop(['time','Time'], axis = 1, inplace = True)
        logger.info('追加点名查询完成!')
        df = read_parquet(path)
        logger.info('加载原始数据集完成!')
        cols_to_use = df.columns.difference(result.columns)
        res = pd.merge(df[cols_to_use], result, left_index=True, right_index=True, how='outer')
        
        static_points = dataset['static_points']
        null_points = dataset['null_points']
        all_points = dataset['all_points']
        
        cols_to_use = result.columns.difference(df.columns)
        for col in cols_to_use:
            all_points.append(col)
            float_col = pd.to_numeric(result[col])
            if math.isclose(float_col.std(), 0, rel_tol=1e-09, abs_tol=0.0):
                static_points.append(col)
            if float_col.isnull().all():
                null_points.append(col)
                    
        table = pa.Table.from_pandas(res)
        pq.write_table(table, path)
        
        r.set(f'did_{did}', 1)            #更新数据集操作状态
        data_size = get_FileSize(path)
        new_data = {}
        new_data['null_points'] = json.dumps(null_points)
        new_data['static_points'] = json.dumps(static_points)
        new_data['all_points'] = json.dumps(all_points)
        new_data['size'] = data_size
        new_data['append_status'] = 1
        new_data['append_process'] = 100.00
        Dataset.update_info(did, new_data)
        data['status'] = '成功'
        data['msg'] = '追加点名成功!'
        logger.info(f"{data}")
    except Exception as e:
        r.set(f'did_{did}', 1)          #更新数据集操作状态
        Dataset.update_info(did, {'append_status':2})
        data['status'] = '失败'
        data['msg'] = '追加点名失败'
        logger.warning(f"{data}")
        logger.warning(f"{e}")
        traceback.print_exc()
    if did in processes:
        processes.pop(did)


#删除数据集中部分点名
@dataset_blueprint.route('/delete_points', methods=['POST'])
@handle_error
def delete_points():
    success, data = get_request_data(request, ['did','points_value'], list_fields=['points_value'])
    if not success:
        return false_return(data)
    points = data['points_value']
    # points = points_value.split(',')
    did = data['did']
    try:
        if len(points):
            is_available = r.get(f'did_{did}')
            if is_available is None or int(is_available) == 1:
                r.set(f'did_{did}', 0)
                dataset = Dataset.get_by_id(did).to_json()
                path = dataset["path"]
                static_points = dataset['static_points']
                null_points = dataset['null_points']
                all_points = dataset['all_points']

                df = read_parquet(path)
                intersection = list(set(df.columns) & set(points))
                static_points = list(set(static_points).difference(intersection))
                null_points = list(set(null_points).difference(intersection))
                all_points = list(set(all_points).difference(intersection))
                
                df.drop(intersection, axis=1, inplace=True)
                table = pa.Table.from_pandas(df)
                pq.write_table(table, path)
                
                r.set(f'did_{did}', 1)          #更新数据集操作状态
                
                data_size = get_FileSize(path)
                new_data = {}
                new_data['null_points'] = json.dumps(null_points)
                new_data['static_points'] = json.dumps(static_points)
                new_data['all_points'] = json.dumps(all_points)
                new_data['size'] = data_size
                Dataset.update_info(did, new_data)
                return true_return(msg="删除点名成功")
            else:
                return false_return(msg='该数据集正在被修改,请稍后重试')
        else:
            return false_return(msg='删除的点名不能为空')
    except Exception as e:
        r.set(f'did_{did}', 1)          #更新数据集操作状态
        logger.warning(str(e))
        return false_return(msg='删除点名失败')


@dataset_blueprint.route('/download/<download_type>', methods=['POST'])
@handle_error
def download_file(download_type):
    """导出influxdb数据生成文件返回 
    Args:
        download_type (str): 指定导出数据的类型, 支持插值与均值
    """
    types = ['average', 'interpolation']
    args = ['sample_step', 'start_time', 'end_time', 'sid']
    if not download_type or download_type not in types:
        return false_return(f'没有相关"{download_type}"的下载类型或未传入该参数')
    success, msg = check_unit()
    if not success:
        return false_return(msg)
    success, data = get_request_data(request, args)
    if not success:
        return false_return("缺少必要参数", data)
    tags_file = request.files.get('tags_file', None)
    if tags_file:
        allowed, filename, extension = allowed_upload_csv(tags_file.filename, allowed_extensions=['xlsx'])
        if not allowed:
            return false_return(msg=f"文件后缀名必须是.xlsx,实际文件名为：{tags_file.filename}")
        
        # f = chardet.detect(tags_file.read())
        # encode = f['encoding']
        tags_file.seek(0)
        excel = pd.read_excel(tags_file, engine='openpyxl')
        tags = excel.columns.values
        logger.info(f"文件上传成功：{tags_file}")
    else:
        logger.error(f"缺少文件：{tags_file}")
        return false_return("请上传文件")
    sample_step = int(data.get('sample_step', '1'))
    start_time = Normaltime(data.get('start_time'))
    end_time = Normaltime(data.get('end_time'))
    sid = data.get('sid', '')
    unit = g.unit
    current = int(time.time())
    path = '/workspace/data/indicators/download_' + str(current) + '.xlsx'
    ctx = multiprocessing.get_context('fork')
    db.get_engine(app=current_app).dispose()
    p = ctx.Process(target=batch_write_to_file, args=(path, sample_step, start_time, end_time, download_type, tags, unit, sid))
    p.start()
    return true_return(msg="正在读取数据生成下载文件")


def batch_write_to_file(path, sample_step, start_time, end_time, download_type, tags, unit, sid):
    """读取influxdb中的数据并进行处理, 将处理结果写入文件, 将生成的地址写入数据库并通过ws返回

    Args:
        path (str): 指定写入文件的路径
        sample_step (int): 指定采样时间步长
        start_time (datetime.datetime): 指定查询的起始时间
        end_time (datetime.datetime): 指定查询的终止时间
        download_type (str): 指定查询类型
        tags (list): 指定需要查询的点名
        unit (int): 指定ws返回的前端所在机组, ws返回机制加入了sid的修改之后暂时没什么用
        sid (str): 指定ws返回的客户端所持有的sid

    Raises:
        IndexError: 没有数据时抛出该异常
    """
    try:
        # sec用于计算进度与估计读取数目total
        sec = (arrow.get(end_time) - arrow.get(start_time)).total_seconds() + 1
        if sec == 0:
            raise Exception("时间范围围为0")
        total = sec // sample_step
        if sec % sample_step != 0:
            total += 1
        logger.info(f"Total size: {total}")
        # 取总数目估计值total的 1 / 10 作为每个chunk的大小
        chunk_size = total // 10
        chunk_count = 0
        db_res, excel_data, columns= list(), list(), list()
        descs = ['时间']
        
        if download_type == 'average':
            # 求均值时, 先读取全部的采样数据, 再根据步长计算均值
            db_res = influx.normal_query(start_time, end_time, tags, chunked=True, chunk_size=chunk_size)
        else: # download_type == 'interpolation'
            # 求插值时, 直接采用步长内最早的数据作为插值
            db_res = influx.query_by_func(sample_step, start_time, end_time, tags, "FIRST", chunked=True, chunk_size=chunk_size)
        if not db_res:
            raise IndexError("没有数据")
        
        for res in db_res:
            if 'series' not in res._raw or not res._raw['series']:
                raise IndexError("没有数据")
            values = res._raw['series'][0]['values']
            if chunk_count == 0:
                columns = res._raw['series'][0]['columns']
                if not columns:
                    raise IndexError("没有数据")
                # 构造第一行数据：点描述
                # columns = reformat_columns(columns, download_type)
                tag_desc_mapper, _ = OriginPointDesc.get_point_descs_by_name(tags)
                for col in columns[1:]:
                    descs.append(tag_desc_mapper.get(col, ''))
            excel_data.extend(values)
            # 用当前所读取到的时间尾与起始时间之间的秒差计算进度, 注意读取出来的默认时间是UTC需要转换
            cur_time = (utc_to_local(excel_data[-1][0]) - start_time).total_seconds() + 1
            cur_process = round(cur_time / sec * 100 , 2)
            # 加入sid让 socket backend 能指定某一个对应的客户端进行emit
            data = {'status':0, 'process':cur_process, 'msg':'正在生成文件', 'iid': '', 'path':'', 'sid': sid}
            send_websocket_msg('download_process', data, room=unit)
            chunk_count += len(values)
            # logger.info(f"Current download process: {cur_process}")
        
        # 时间转换比较耗时, 占到总时间的1/2 ~ 2/3
        for row in excel_data:
            row[0] = utc_to_local(row[0])
        df = pd.DataFrame(excel_data, columns=columns)
        df = df.fillna(method='bfill')
        df = df.fillna(method='ffill')
        
        if download_type == 'average':
            values = get_avg_values(df.values, sample_step)
            df = pd.DataFrame(values, columns=columns)
        
        df = df.fillna('')
        df_desc = pd.DataFrame([descs], columns=columns)
        df = pd.concat([df_desc, df], ignore_index=True)
        
        df.to_excel(path, sheet_name=download_type, index=False)
        
        # 将下载历史写入mysql
        size = os.stat(path).st_size
        iid = Indicator.create(time=DT.now(), path=path, size=size)
        data = {'status':1, 'process': 100.00, 'msg':'文件生成完毕', 'iid': iid, 'path': trans_path(path), 'sid': sid}
        send_websocket_msg('download_process', data, room=unit)
        logger.info(f'文件生成完毕!路径位于{path}')
    except IndexError as ie:
        data = {'status':2, 'process': 0.00, 'msg':'没有数据', 'iid': '', 'path':'', 'sid': sid}
        send_websocket_msg('download_process', data, room=unit)
        traceback.print_exc()
        logger.warning('没有数据:', str(ie))
    except Exception as e:
        data = {'status':3, 'process': 0.00, 'msg':f'下载异常：{str(e)}', 'iid': '', 'path':'', 'sid': sid}
        send_websocket_msg('download_process', data, room=unit)
        traceback.print_exc()
        logger.error(str(e))
    finally:
        return


def get_avg_values(values, sample_step) -> list:
    """对读取到的采样数据按步长求均值

    Args:
        values (numpy.ndarray): 需要处理的采样数据, 二维数组
        sample_step (int): 指定步长

    Returns:
        list: 求均值完毕后的均值数据
    """
    res = list()
    st = values[0][0]
    # 第一列是时间, 剩下的是需要处理的数据
    all_data = np.array(values[:, 1:], dtype=np.float32)
    m = 0
    pre_t = st
    for i,value in enumerate(values):
        t = value[0]
        dt = (t - st).total_seconds()
        nt = (t - pre_t).total_seconds()
        # 最后一截不满足sample_step长度的数据被丢弃
        if (dt != 0 and dt % sample_step == 0) or (nt >= sample_step):
            avg = np.sum(all_data[m:i], axis=0)
            avg = avg / sample_step
            r = [t]
            r.extend(avg)
            res.append(r)
            m = i
            pre_t = t
    return res


def trans_path(path):
    l = len('/workspace/data')
    return path[l:]

# def reformat_columns(columns, dtype):
#     """ 去除查询前缀 """
#     for i,col in enumerate(columns):
#         l = 0
#         if dtype == 'average':
#             l = len('mean_')
#         else:
#             l = len('first_')
#         if col == 'time':
#             continue
#         columns[i] = col[l:]
#     return columns


@dataset_blueprint.route('/download_link/<iid>', methods=['GET'])
@handle_error
def get_links_by_iid(iid):
    if not iid:
        return false_return("参数异常", iid)
    res = Indicator.get_by_id(iid).to_dict()
    res['path'] = trans_path(res['path'])
    return true_return('查询成功', data=res)


@dataset_blueprint.route('/download_links', methods=['GET'])
@handle_error
def get_all_links():
    res, _ = Indicator.get_all()
    if not len(res):
        return false_return('没有查到任何数据')
    data = list()
    for r in res:
        d = r.to_dict()
        d['path'] = trans_path(d['path'])
        data.append(d)
    return true_return('查询成功', data=data)


@dataset_blueprint.route('/download_links', methods=['DELETE'])
@handle_error
def delete_all_links():
    Indicator.clear()
    path = '/workspace/data/indicators'
    files = os.listdir(path)
    for f in files:
        os.remove(os.path.join(path, f))
    return true_return("历史清除成功！")


# @dataset_blueprint.route('/test_wbskt/<sid>', methods=['GET'])
# @handle_error
# def test_wbskt(sid):
#     logger.info(f"Backend get sid: {sid}")
#     data = {"msg": "test send msg", "sid": sid}
#     send_websocket_msg('download_process', data, room=3)
#     return true_return("test")


##################add-begin-2-15-12:54
# @dataset_blueprint.route('/get_abnormal_point', methods=['GET'])
# @handle_error
# def get_abnormal_point():
#     from flask_app.util.process_manager import add_dataset_processes
#     sample_step = g.data.get('sample_step')
#     sample_step = int(sample_step)
#     duration = g.data.get('duration')
#     duration = int(duration)
#     start_time = g.data.get('start_time')
#     start_time = Normaltime(str(start_time))
#     drop_null = g.data.get('drop_null')
#     drop_null = int(drop_null)
#     drop_unchanging = g.data.get('drop_unchanging')
#     drop_unchanging = int(drop_unchanging)
#     tags = []
#     if session.get('tags'):
#         for tag in session['tags']:
#             tags.append(tag)
#     try:
#         p = multiprocessing.Process(target=get_abnormal_point, args=(sample_step, duration, start_time, drop_null, drop_unchanging, tags, add_dataset_processes))
#         p.start()
#         return true_return(msg="创建查询成功")
#     except:
#         return false_return(msg="创建查询失败")
# def get_abnormal_point(sample_step, duration, start_time, drop_null, drop_unchanging, selected_tags, processes):
#     pid = os.getpid()
#     data = {}
#     try:
#         processes.append(pid)
#         res = influx.query(sample_step, duration, start_time)
#         if res:
#             data = preprocessing(1, res, drop_null, drop_unchanging, selected_tags)
#             send_websocket_msg('abnormal_point', data, broadcast=True, namespace='/websocket')
#         else:
#             data = {'msg':'该时段没有数据,请重新选择'}
#             send_websocket_msg('abnormal_point', data, broadcast=True, namespace='/websocket')
#     except Exception as e:
#         data['status'] = '失败'
#         data['exception'] = str(e)
#         send_websocket_msg('abnormal_point', data, broadcast=True, namespace='/websocket')
#     if pid in processes:
#         processes.remove(pid)


# @dataset_blueprint.route('/add_with_preprocessing', methods=['POST'])
# @handle_error
# def add_new_dataset_pre():
#     from flask_app.util.process_manager import add_dataset_processes
#     sample_step = g.data.get('sample_step')
#     sample_step = int(sample_step)
#     duration = g.data.get('duration')
#     duration = int(duration)
#     name = g.data.get('name')
#     current = int(time.time())
#     path = '/workspace/data/' + name + '_' + str(current) + '.pickle'
#     start_time = g.data.get('start_time')
#     start_time = Normaltime(start_time)
#     tags = []
#     if session.get('tags'):
#         for tag in session['tags']:
#             tags.append(tag)
#     drop_null = g.data.get('drop_null')
#     drop_null = int(drop_null)
#     drop_unchanging = g.data.get('drop_unchanging')
#     drop_unchanging = int(drop_unchanging)

#     try:
#         p = multiprocessing.Process(target=add_new_dataset_pre, args=(sample_step, duration, name, path, start_time, tags, add_dataset_processes, drop_null, drop_unchanging))
#         p.start()
#         return true_return(msg="add_with_preprocessing创建成功..")
#     except:
#         return false_return(msg="add_with_preprocessing创建失败..")

# def add_new_dataset_pre(sample_step, duration, name, path, start_time, selected_tags, processes, drop_null, drop_unchanging):
#     pid = os.getpid()
#     data = {
#         "name": name,
#         "path": path
#     }
#     try:
#         processes.append(pid)
#         res = influx.query(sample_step, duration, start_time)
#         if res:
#             res = preprocessing(2, res, drop_null, drop_unchanging, selected_tags)
#             if res:
#                 save_pickle_raw(res, path)
#                 Dataset.add(sample_step, duration, path, start_time, name)
#                 data['status'] = '成功'
#                 send_websocket_msg('add_dataset', data, broadcast=True, namespace='/websocket')
#             else:
#                 data['status'] = '失败'
#                 data = {'msg':'处理后数据为空,创建失败'}
#                 send_websocket_msg('add_dataset', data, broadcast=True, namespace='/websocket')
#         else:
#             data = {'msg':'该时段没有数据,请重新选择'}
#             send_websocket_msg('abnormal_point', data, broadcast=True, namespace='/websocket')
#     except Exception as e:
#         data['status'] = '失败'
#         data['exception'] = str(e)
#         send_websocket_msg('add_dataset', data, broadcast=True, namespace='/websocket')
#     if pid in processes:
#         processes.remove(pid)

# def preprocessing(step, res, drop_null=0, drop_unchanging=0, selected_tags = []):
#     tdata = res._raw['series'][0]['values']
#     tcolumns = res._raw['series'][0]['columns']
#     for index in range(len(tcolumns)):
#         if tcolumns[index].startswith('first_'):
#             tcolumns[index] = tcolumns[index].strip('first_')
#     selected_keys = []
#     keys_index = {}
#     temp = []
#     for key in selected_tags:
#         if key in tcolumns:
#              keys_index[tcolumns.index(key)] = key
#              selected_keys.append(key)
#     if len(selected_keys):
#         for item in tdata:
#             for index in range(len(item)):
#                 if index in keys_index.keys():
#                     temp.append(item[index])
#             item.clear()
#             for key in temp:
#                 item.append(key)
#             temp.clear()
#         pdata = pd.DataFrame(tdata, columns=selected_keys)
#     else:
#         pdata = pd.DataFrame(tdata, columns=tcolumns)
#     unchanging = []
#     for col in pdata.columns[1:-1]:
#         if pdata[col].std() == 0:
#             unchanging.append(col)
                
#     if step == 1:
#         null_points = None
#         unchanging_points = None
#         if drop_null:
#             null_points = []
#             rdata = pdata.dropna(axis = 'columns', how = 'all')
#             notnull = list(rdata.columns)
#             for c in tcolumns:
#                 if c not in notnull:
#                     null_points.append(c)
#         if drop_unchanging:
#             unchanging_points = unchanging
#         return {'null_points':null_points, 'unchanging_points':unchanging_points}
#     elif step == 2:
#         if drop_null:
#             pdata = pdata.dropna(axis = 'columns', how = 'all')
#         if drop_unchanging:
#             pdata = pdata.drop(unchanging, axis=1)
#         res._raw['series'][0]['values'] = pdata.values.tolist()
#         res._raw['series'][0]['columns'] = list(pdata.columns)
#         return res
# ##################add-end-2-15-12:54

# def pre_processing(sample_step, start_time, end_time, selected_tags, drop_null=0, drop_unchanging=0, path = ''):
    
    
#     pdata = pd.DataFrame(tdata, columns=tcolumns)
#     pdata = pdata.fillna(method='ffill')
#     pdata = pdata.fillna(method='bfill')
#     pdata.drop('time',axis = 1,inplace = True)
    
#     static_points = []
#     null_points = []

#     for col in pdata.columns:
#             if math.isclose(pdata[col].std(), 0, rel_tol=1e-09, abs_tol=0.0):
#                 static_points.append(col)
#             if pdata[col].isnull().all():
#                 null_points.append(col)
#     print(len(null_points))
#     print(len(static_points))
#     if drop_null:
#         pdata = pdata.dropna(axis = 'columns', how = 'all') 
#     if drop_unchanging:
#         pdata = pdata.drop(static_points, axis=1)
    
#     pdata.to_pickle(path)
#     abnormal_points = {}
#     abnormal_points['null_points'] = null_points
#     abnormal_points['static_points'] = static_points
#     return abnormal_points