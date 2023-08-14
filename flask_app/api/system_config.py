import csv
import json
import traceback
import multiprocessing
import pandas as pd
from typing import Dict, List, Tuple, Union

from pandas import DataFrame

from flask import Blueprint, g, request, current_app
from flask_app import redis, result_redis, db
from flask_app.api import handle_error
from flask_app.common.before_request import check_page, get_request_data, check_unit
from flask_app.common.result import false_return, true_return
from flask_app.util.common.time_trans import *
from flask_app.models.origin_point_dec import OriginPointDesc, PointType, write_origin_points_to_redis
from flask_app.models.point_desc import PointDesc
from flask_app.models.system_config import SystemConfig
from flask_app.models.origin_point_system_config import OriginPointSystemConfig
from flask_app.models.relation_map import add_all, clear_origin_point_system_table, upsert_all
from flask_app.util.common.file_os import allowed_upload_csv
from flask_app.common.update import update
from flask_app.util.file_util import get_file_encoding, store_request_file

sysconfig_blueprint = Blueprint("sysconfig_blueprint", __name__, url_prefix='/sysconfig')

system_dict: Dict[str, int] = {}
system_children_dict: Dict[str, List[str]] = {}
sub_system_dict: Dict[str, SystemConfig] = {}

system_tree = dict()

def get_redis_system_tree():
    s = redis.read("system_tree") or "{}"
    return json.loads(s)

def set_redis_system_tree(system_tree:Dict):
    redis.write("system_tree",json.dumps(system_tree))
    redis.persist("system_tree")

@sysconfig_blueprint.before_request
@handle_error
def before_request():
    success, msg = check_unit()
    if not success:
        return false_return(msg)
    if request.method == 'GET' or request.method == 'DELETE':
        g.data = request.args
    else:
        if "form-data" in request.content_type:
            g.data = request.form
        else:
            g.data = request.get_json()


@sysconfig_blueprint.route('/upload_file', methods=['POST'])
@handle_error
def upload_file():
    try:
        # 只上传一个文件，包括三列：英文点名 中文点名 对应系统名（英文可以属于多个系统，空格隔开）
        sysconfig_file = request.files.get('sysconfig_file', None)
        if sysconfig_file is None:
            return false_return("请上传文件")

        data = request.form
        if data and data.get("clear", False):
            clear_table(g.unit)
        
        allowed, filename, extension = allowed_upload_csv(sysconfig_file.filename)
        if not allowed:
            return false_return("文件后缀名必须是.csv")
        
        # 存储到本地文件夹中
        path = store_request_file(sysconfig_file, filename, prefix="_sysconfig_")
        encoding = get_file_encoding(path)
        
        # 由于系统表(system_config)基本不发生变化，因此可用一次性判断
        # 只连一次数据库，后面可以考虑用redis来维护一个哈希，此处暂时用dict哈希代替
        sys_total = SystemConfig.get_all_id_and_names_in_unit(g.unit)
        sys_name_list = []
        # key => name, value => cid  注意：应确保每个系统name对应唯一 一个cid，才能根据该方法进行索引
        for row in sys_total:
            sys_name_list.append((row.name, row.cid))
        sys_name_list = dict(sys_name_list)
        
        db.get_engine(app=current_app).dispose()
        ctx = multiprocessing.get_context('spawn')
        p = ctx.Process(target=batch_create_sysconfig_originpoint_by_file, args=(path, sys_name_list, g.unit, encoding))
        p.start()
        return true_return("正在批量创建原始点", None)
        # result = batch_create_sysconfig_originpoint_by_file(path=path, encoding=encoding)
        # if result:
        #     write_origin_points_to_redis(origin_point=True, inter_variable=False)
        #     return true_return("批量添加成功", None)
        # else:
        #     return false_return("相关系统不存在或数据格式错误等其他错误，请检查后重新上传", None)
        
        # sysconfig_file = request.files.get('sysconfig_file' , None)
        # alias_file = request.files.get('alias_file', None)
        # data = request.form
        # if data and data.get("clear", False):
        #     clear_table(g.unit)

        # if sysconfig_file is None or alias_file is None:
        #     return false_return(f"请上传文件")
        # sysconfig_file_allowed, sysconfig_file_filename, sysconfig_file_extension = allowed_upload_csv(sysconfig_file.filename)
        # alias_file_allowed, alias_file_filename, alias_file_extension = allowed_upload_csv(alias_file.filename)
        # if not (sysconfig_file_allowed and alias_file_allowed):
        #     error_message = "文件后缀名必须是.csv"
        #     return false_return(error_message)

        # sysconfig_path = store_request_file(sysconfig_file, sysconfig_file_filename, prefix="_sysconfig_", suffix="_bulk")
        # alias_path = store_request_file(alias_file, alias_file_filename, prefix="_alias_", suffix="_bulk")

        # encoding = get_file_encoding(sysconfig_path)
        # sysconfig_result, sysconfig_msg = bulk_add_origin_points_from_file(sysconfig_path, encoding)
        # if sysconfig_result is False:
        #     return false_return(sysconfig_msg)
        # else:
        #     # 创建成功则清空system关系
        #     set_redis_system_tree({})
        #     system_dict.clear()
        #     sub_system_dict.clear()
        #     system_children_dict.clear()
        #     write_origin_points_to_redis(origin_point=True, inter_variable=False)

        # encoding = get_file_encoding(alias_path)
        # alias_result, alias_msg = add_alias(alias_path, encoding=encoding)
        # if alias_result:

        #     return true_return("批量添加成功")
        # else:
        #     return false_return(alias_msg)
    except UnicodeDecodeError as decode_error:
        traceback.print_exc()
        return false_return('文件编码错误,无法解析,文件编码格式应为UTF-8 或 GBK 或 GB2312: ' + str(decode_error))
    except Exception as e:
        traceback.print_exc()
        return false_return('未知异常,%s' % str(e))


def batch_create_sysconfig_originpoint_by_file(path: str, sys_name_mapper: dict, unit: Union[str, int], encoding='utf-8'):
    """
    通过文件的数据多进程批量创建

    Args:
        path (str): 具体数据(已经保存成文件)路径
        sys_name_mapper (dict): 用于检索的 系统名称<=>cid 索引
        unit (Union[str, int]): 机组名
        encoding (str): 数据文件编码
    """
    # pool_size = 60
    
    data: DataFrame = pd.read_csv(path, encoding=encoding)
    # NaN数据缺失部分替换为''
    data = data.where(data.notnull(), '')
    
    for row in data.itertuples(index=False):
        try:
            # 建一个进程池
            # pool = multiprocessing.Pool(pool_size)
            sys_str = str(getattr(row, '对应系统名'))
            if sys_str:
                sys_list = str(sys_str.split(' '))
            else:
                sys_list = []
            tag_name = getattr(row, '英文点名').strip()
            describe = getattr(row, '中文点名').strip()
            success, msg = OriginPointDesc.upsert_all([OriginPointDesc(tag_name=tag_name, describe=describe, unit=unit)])
            if success:
                # 每条记录的对应系统可能有多个
                sys_list_filter, confs = [], []
                for sys in sys_list:
                    if sys in sys_name_mapper.keys():
                        sys_list_filter.append(sys_name_mapper.get(sys))
                
                for cid in sys_list_filter:
                    confs.append(OriginPointSystemConfig(origin_point=tag_name, system_config=cid).to_dict())
                if len(confs):
                    OriginPointSystemConfig.upsert_all(records=confs)
            else:
                raise Exception(msg)
            # pool.close()
            # pool.join()
        except Exception as err:
            print('error occurs when upserting origin points: ', str(err))
            traceback.print_exc()
            continue
    write_origin_points_to_redis(origin_point=True, inter_variable=False)
    # confs, origin_points, sys_name_list = [], [], []
    # try:
    #     # 逐行读取判断，上传的系统若存在则批量插入
    #     for row in data.itertuples(index=False):
    #         sys_list = getattr(row, '对应系统名').split(' ')
    #         tag_name = getattr(row, '英文点名')
    #         describe = getattr(row, '中文点名')
    #         # if check:
    #         sys_list_filter = []
    #         for sys in sys_list:
    #             if sys in sys_name_list.keys():
    #                 sys_list_filter.append(sys_name_list.get(sys))
            
    #         if not len(sys_list_filter):
    #             # 所有系统里面没有一个是存在的，该条记录可以跳过(continue)也可以选择插入该条记录，待定。
    #             continue
    #         else:
    #             # 没有使用flask-sqlalchemy，而是直接用的sqlalchemy，所以插入数据的格式不同
    #             for cid in sys_list_filter:
    #                 confs.append(OriginPointSystemConfig(origin_point=tag_name, system_config=cid).to_dict())
    #         origin_points.append(OriginPointDesc(tag_name=tag_name, describe=describe, unit=g.unit).to_dict())
    #     # add_all(origin_points)
    #     # add_all(confs)
    #     # 为了确保并发下的数据一致性，选择sql层面的upsert进行实现
    #     upsert_all(OriginPointDesc, origin_points)
    #     upsert_all(OriginPointSystemConfig, confs)
    #     return True
    # except Exception as e:
    #     traceback.print_exc()
    #     return False


@sysconfig_blueprint.route('/system', methods=['GET'])
@handle_error
def query_systems():
    """
    查询系统信息
    ----------
    Args:
        cid: 系统id
    ----------
    """
    have_id, data = get_request_data(request, ['cid'])
    # 如果请求参数中不存在cid，则返回unit的全部system信息
    if not have_id:
        have_page, page, size = check_page(request)
        if have_page:
            sys_conf, total = SystemConfig.get_by_page(g.unit, page, size)
        else:
            sys_conf, total = SystemConfig.get_all_in_unit(g.unit)
        result = {
            'total': total,
            'systems': [s.to_json(full=False) for s in sys_conf]
        }
        return true_return("查询成功", result)
    # 存在cid，根据cid获取system信息
    else:
        cid = data['cid']
        sys_conf = SystemConfig.get_by_id(cid, g.unit)
        if sys_conf is not None:
            return true_return("查询成功", sys_conf.to_json())
        else:
            return false_return("查询失败, unit:{} cid:{} 不存在".format(g.unit, cid))


@sysconfig_blueprint.route('/system', methods=['POST'])
@handle_error
def add_system_config():

    success, data = get_request_data(request, ['name', 'alias'])
    if not success:
        return false_return(data)
    system_name = data['name']
    system_alias = data['alias']
    parent_sys_id = g.data.get('parent')
    system_config = SystemConfig.get_by_name(system_name, g.unit)
    if system_config is not None:
        cid=system_config.cid
        updatasuccess,updatamsg = SystemConfig.update_system_config(cid,data) #出现重复则进行更新
        if updatasuccess:
            system_tree = get_redis_system_tree()
            system_tree[g.unit] = list()
            set_redis_system_tree(system_tree)
            return true_return('更新成功')
        else:
            return false_return(updatamsg)
    if parent_sys_id:
        target_sys = SystemConfig.get_by_id(parent_sys_id, g.unit)
        if not target_sys:
            return false_return('找不到指定的上级系统')

    SystemConfig.create_system_config(system_name, parent_sys_id, system_alias, g.unit)
    
    system_tree = get_redis_system_tree()
    system_tree[g.unit] = list()
    set_redis_system_tree(system_tree)
    return true_return('创建成功')


@sysconfig_blueprint.route('/system', methods=['PUT'])
@handle_error
def modify_system_config():
    success, data = get_request_data(request, ['cid'])
    if not success:
        return false_return(data)

    cid = data['cid']
    system = SystemConfig.get_by_id(cid, g.unit)
    if not system:
        return false_return('找不到指定系统cid-{}'.format(cid))

    update_data = update(g.data, ['name', 'alias', 'parent'])
    db_success, msg = SystemConfig.update_system_config(cid, update_data)
    if db_success:
        system_tree = get_redis_system_tree()
        system_tree[g.unit] = list()
        set_redis_system_tree(system_tree)
        return true_return('修改成功')
    else:
        return false_return(msg)


@sysconfig_blueprint.route('/system', methods=['DELETE'])
@handle_error
def delete_system_config():
    success, data = get_request_data(request, ['cid'])
    if not success:
        return false_return(data)

    cid = data['cid']
    target_sys = SystemConfig.get_by_id(cid, g.unit)
    if not target_sys:
        return false_return('找不到指定系统')

    if target_sys.children:
        return false_return('请先删除所包含的子系统')

    SystemConfig.delete_system_config(cid)
    system_tree = get_redis_system_tree()
    system_tree[g.unit] = list()
    set_redis_system_tree(system_tree)
    return true_return('删除成功')


@sysconfig_blueprint.route("/add_origin_points", methods=['POST'])
@handle_error
def add_points_to_system():
    is_tag_name, data1 = get_request_data(request, ['cid', 'tag_names'], ['tag_names'])
    is_point_name, data2 = get_request_data(request, ['cid', 'point_names'], ['point_names'])
    if is_tag_name:
        cid = data1['cid']
        names = data1['tag_names']
    elif is_point_name:
        cid = data2['cid']
        names = data2['point_names']
    else:
        return false_return(f"{data1} or {data2}")
    target_sys = SystemConfig.get_by_id(cid, g.unit)
    if target_sys is None:
        return false_return('找不到指定系统')

    msg = SystemConfig.modify_origin_points_to_systems(cid, tag_names=names, unit=g.unit)
    return true_return(msg)


@sysconfig_blueprint.route('/point', methods=['GET'])
@handle_error
def query_point():
    """
    查询原始点或者系统所属的原始点
    不能在使用pid来查询，
    ----------
    Args:
        name: 点名
        cid: 系统id
    ----------
    Returns:
        point: 点描述对象（单个对象或列表）
    """

    have_name, data = get_request_data(request, ['name'])
    if have_name:
        p_name = data['name']
        res = OriginPointDesc.get_by_name(p_name, None)
        if not res:
            res = None
            return false_return('找不到指定的点')
        else:
            res = res.to_json()
        return true_return('查询成功', res)

    have_cid, data = get_request_data(request, ['cid'])
    if have_cid:
        cid = data['cid']
        system = SystemConfig.get_by_id(cid, g.unit)
        if not system:
            return false_return('找不到指定系统cid-{}'.format(cid))
        res = get_children_points(system)
        have_filter, _ = get_request_data(request, ['filter'])
        if have_filter:
            res = filter_origin_points(res)
            return true_return("filter", res)
        return true_return("ok", res)

    # 如果id,name,cid都不存在,则获取unit中全部PointDesc
    have_page, page, size = check_page(request)
    points, total = OriginPointDesc.get_by_page(page, size, g.unit)
    res = {
        'points': [p.to_json(full=True) for p in points],
        'total': total
    }
    return true_return('查询成功', res)


@sysconfig_blueprint.route('/point_names', methods=['POST'])
def get_multi_points():
    '''
    通过点英文名一次获取多个原始点的信息
    '''
    success, data = get_request_data(request, ['names'], ['names'])
    if not success:
        return false_return(data)

    point_names = data['names']
    origin_points = OriginPointDesc.get_origin_points_by_names(point_names, g.unit)

    return true_return('查询成功', [p.to_json() for p in origin_points])


@sysconfig_blueprint.route('/system_score', methods=['GET'])
def get_score_of_system():
    '''
    获取指定系统的健康度(评分, 0-100)
    '''
    success, data = get_request_data(request, ['cid'])
    if not success:
        return false_return(data)

    cid = data['cid']
    target_system = SystemConfig.get_by_id(cid, g.unit)
    if not target_system:
        return false_return('找不到指定系统')

    if target_system.children:
        all_scores = list()
        child_systems = SystemConfig.get_by_parent(cid)
        for child in child_systems:
            success, msg, score = get_system_score(child)
            score_info = child.to_json(full=False)
            score_info['score'] = score
            all_scores.append(score_info)
        res = {
            'system_score': sum(map(lambda x: x['score'], all_scores)) / len(all_scores),
            'children_scores': all_scores
        }
        return true_return('查询成功', res)
    success, msg, score = get_system_score(target_system)
    if not success:
        return false_return(msg, score)
    return true_return(msg, score)

def get_score_of_all_system(cid, unit):
    target_system = SystemConfig.get_by_id(cid,unit)
    if not target_system:
        raise ValueError("找不到指定系统")

    if target_system.children:
        all_scores = list()
        child_systems = SystemConfig.get_by_parent(cid)
        for child in child_systems:
            success, msg, score = get_system_score(child)
            score_info = child.to_json(full=False)
            score_info['score'] = score
            all_scores.append(score_info)
        res = {
            'system_score': sum(map(lambda x: int(x['score']), all_scores)) / len(all_scores),
            'children_scores': all_scores
        }
        return res 
    
    success, msg, score = get_system_score(target_system)
    if not success:
        raise ValueError("获取系统评分错误")
    return score

def get_system_score(target_system: SystemConfig):
    '''
    获取系统评分
    首先查询是否有对应的异常检测模型的预测结果, 若找不到模型结果, 则根据系统内报警点的个数按比例给出评分
    ----------
    Args:
        target_system: 系统model对象
    Returns:
        success: bool, 是否成功执行
        msg: str, 成功或失败信息
        score: float, 评分; 出错时为默认值100
    '''
    score = 100  # 默认为100分

    if not target_system:
        return False, '找不到指定系统', score
    cid = target_system.cid

    ts = redis.read('latest')
    if ts is not None:
        ts = int(ts)
        key = 'Subsystem{}-{}'.format(cid, ts)
        # {'ts': 时间戳, 'value': 异常指数, 'contribution': 贡献}
        model_res = result_redis.read(key)
        # if model_res:
        #     model_res = json.loads(model_res)
        #     anomany_rate = model_res['value']
        #     score = 100 - anomany_rate
        #     score = max(0, score)  # 最低为0分
        #     return True, '获得来自模型的评分', score

        # # 如果无法获取到模型结果
        # target_system = SystemConfig.get_by_id(cid, unit)
        # if not target_system:
        #     return False, '找不到指定系统', score

        point_names = list()
        for p in target_system.origin_points:
            point_names.append(p.tag_name)
        if len(point_names) ==0:
            return True, '子系统无点名', format(100, '.3f')
        warnings_ts = result_redis.read('warnings-latest')
        keys = ['{}-{}-warnings'.format(point_name, warnings_ts)
                for point_name in point_names]
        # [[{'type': '', msg: ''}, {}, ...], [...], ...]
        # print(keys)
        warnings = result_redis.redis_client.mget(*keys)
        n_warn_points = 0
        for point_warning_json_str in warnings:
            if point_warning_json_str is None:
                continue
            point_warning = json.loads(point_warning_json_str)
            if point_warning:
                n_warn_points += 1
        score = min(pow(max(len(keys) - n_warn_points,0)/len(keys),2)*100,100-min(n_warn_points*10,100)) # (1 - n_warn_points / len(keys)) * 100
        return True, '根据报警点的个数获得评分', score

    return True, '找不到实时数据，返回默认值', format(score, '.3f')


@sysconfig_blueprint.route('/multi_search', methods=['GET'])
def multi_search():
    """
    多条件查询原始点信息
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

    selected_points, total = OriginPointDesc.search_all(point_name, point_desc, system, system_alias, g.unit, page, size)

    res = {
        'points': [p.to_json() for p in selected_points],
        'total': total
    }

    return true_return('筛选成功', res)


@sysconfig_blueprint.route('point', methods=['POST'])
def create_point():
    success, data = get_request_data(request, ['name', 'desc'])
    if not success:
        return false_return(data)

    # 创建点名
    point_name = data['name']
    existed_point = OriginPointDesc.get_by_name(point_name, g.unit)
    if existed_point:
        return false_return('点名重复')

    point_desc = data['desc']
    origin_point = OriginPointDesc.create_origin_point_desc(tag_name=point_name, describe=point_desc, unit=int(g.unit))
    write_origin_points_to_redis(origin_point=True, inter_variable=False)
    return true_return('创建成功', origin_point.to_json())


@sysconfig_blueprint.route('point', methods=['DELETE'])
@handle_error
def delete_point():
    """
    删除原始点
    """
    success, data = get_request_data(request, ['name'])
    if not success:
        return false_return(data)

    name = data['name']
    point = OriginPointDesc.get_by_name(name, g.unit)

    if not point:
        return false_return('找不到指定点')

    # 删除点名
    OriginPointDesc.delete_origin_point(name, g.unit)
    write_origin_points_to_redis(origin_point=True, inter_variable=False)
    return true_return(msg='删除成功')


@sysconfig_blueprint.route('point', methods=['PUT'])
@handle_error
def update_point():
    """更新原始点
    """
    success, data = get_request_data(request, ['point_name'])
    if not success:
        return false_return(data)

    point_name = data['point_name']
    target_point = OriginPointDesc.get_by_name(point_name, g.unit)
    if not target_point:
        return false_return('找不到指定点')

    describe = g.data.get("desc")
    if describe is None:
        return false_return("点描述不能为空")
    OriginPointDesc.set_desc(point_name, describe, g.unit)
    return true_return('修改成功')


@sysconfig_blueprint.route('point/systems_belong', methods=['POST'])
@handle_error
def add_systems_to_point():
    success, data = get_request_data(request, ['point_name', 'systems'], ['systems'])
    if not success:
        return false_return(data)

    tag_name = data['point_name']
    target_point = OriginPointDesc.get_by_name(tag_name, g.unit)
    if not target_point:
        return false_return('找不到指定点')

    system_names = data['systems']

    info = OriginPointDesc.add_systems(tag_name, system_names, g.unit)
    msg = info if info != '' else '系统添加成功'
    return true_return(msg)


@sysconfig_blueprint.route('point/systems_belong', methods=['DELETE'])
@handle_error
def remove_systems_from_point():
    success, data = get_request_data(request, ['point_name', 'system'])
    if not success:
        return false_return(data)

    tag_name = data['point_name']
    target_point = OriginPointDesc.get_by_name(tag_name, g.unit)
    if not target_point:
        return false_return('找不到指定点')

    system_names = data['system']

    info = OriginPointDesc.delete_systems(tag_name, system_names, g.unit)
    msg = info if info != '' else '系统移除成功'
    return true_return(msg)


@sysconfig_blueprint.route('/system_tree', methods=['GET'])
@handle_error
def get_system_tree():
    """
    获得多级系统的树状结构
    ----------
    Args:
    ----------
    Returns:
    """
    # global system_tree
    current_unit = g.unit
    need_score = g.data.get('need_score', False)
    system_tree = get_redis_system_tree()
    if not need_score and current_unit in system_tree and len(system_tree[current_unit]) > 0:
        msg = 'ok (from buffer)'
    else:
        system_tree[current_unit] = list()
        set_redis_system_tree(system_tree)
        all_systems = SystemConfig.get_all_id_and_names_in_unit(g.unit)
        # (cid, name, alias, parent, children)元组列表
        # all_systems, _ = SystemConfig.get_all_in_unit(g.unit)

        name_map = dict()
        for sys in all_systems:
            if sys[1] not in name_map:
                name_map[sys[1]] = {
                    'id': sys[0],
                    'name': sys[1],
                    'alias': sys[2],
                    'children': sys[4]
                }
        # for sys in all_systems:
        #     if sys.name not in name_map:
        #         sys_info = {
        #             'id': sys.cid,
        #             'name': sys.name,
        #             'alias': sys.alias,
        #             'children': sys.children
        #         }
        #         if need_score:
        #             success, msg, score = get_system_score(sys)
        #             sys_info['score'] = score
        #         name_map[sys.name] = sys_info

        for sys in all_systems:
            # if not sys.parent:
            # system_tree.append(rec_get_child(sys.name, name_map))
            if not sys[3]:
                system_tree[current_unit].append(rec_get_child(sys[1], name_map))
        msg = 'ok'
    set_redis_system_tree(system_tree)
    return true_return(msg, system_tree[current_unit])


def rec_get_child(child_name, name_map):
    child_dict = name_map[child_name]
    if child_dict['children'] is not None and child_dict['children'] != '':
        child_dict['children'] = [rec_get_child(name, name_map) for name in child_dict['children'].split(',')]
    return child_dict


def save_db(save_filename, encoding='gb2312'):
    """
    将上传的csv文件内容存储到mysql数据库中
    ----------
    Args:
        save_filename: 文件存储的文件地址
    ----------
    Returns:
    """
    system_id = 0
    sub_systems = []
    ORIGIN_POINT_DICT = {}
    # print("save_filename", save_filename)
    with open(save_filename, 'r', encoding=encoding) as f:
        reader = csv.reader(f)
        rows = [row for row in reader]
        table_length = len(rows)
        table_header = rows[0]
        root_sys_index = table_header.index('大系统')
        sub_sys_index = table_header.index('子系统')
        point_name_index = table_header.index('点名')
        point_desc_index = table_header.index('点描述 ')
        for i in range(1, table_length):
            row_content = rows[i]
            root_sys = row_content[root_sys_index]
            sub_sys = row_content[sub_sys_index]
            point_name = row_content[point_name_index]
            point_desc = row_content[point_desc_index]
            # if system_dict.__contains__(root_sys) == False and root_sys != "":
            # system_dict 记录大系统信息, system_children_dict 记录大系统的子系统信息
            # 判断是否system_dict已经记录大系统
            # 如果没有记录，则添加并创建，已有记录则记录信息
            if root_sys != "":
                if root_sys not in system_dict:
                    system_id += 1
                    system_dict[root_sys] = system_id
                    system_children_dict[root_sys] = [sub_sys] if sub_sys != "" else []

                    SystemConfig.create_system_config(root_sys, parent=None, alias=None, unit=g.unit,
                                                      children=",".join(system_children_dict[root_sys]))
                elif root_sys in system_dict:
                    system_children_dict[root_sys].append(sub_sys)
                    root_sys_id = system_dict[root_sys]
                    SystemConfig.update_system_config(root_sys_id,
                                                      dict(children=",".join(set(system_children_dict[root_sys]))))
                """
                 system_dict -> Dict[root_sys:system_id]
                 判断 OriginPointDesc 是否存在，不存在则创建并建立与SystemConfig的关系
                 """
            if sub_sys != "":
                if sub_sys not in sub_system_dict:
                    sub_system = SystemConfig(name=sub_sys, parent=system_dict[root_sys], alias=None, unit=g.unit)
                    sub_system_dict[sub_sys] = sub_system
                    if point_name in ORIGIN_POINT_DICT:
                        origin_point = ORIGIN_POINT_DICT[point_name]
                    else:
                        origin_point = OriginPointDesc(tag_name=point_name, describe=point_desc, unit=g.unit)
                        ORIGIN_POINT_DICT[point_name] = origin_point
                    sub_system.origin_points.append(origin_point)
                elif sub_sys in sub_system_dict:
                    if point_name in ORIGIN_POINT_DICT:
                        origin_point = ORIGIN_POINT_DICT[point_name]
                    else:
                        origin_point = OriginPointDesc(tag_name=point_name, describe=point_desc, unit=g.unit)
                        ORIGIN_POINT_DICT[point_name] = origin_point
                    sub_system_dict[sub_sys].origin_points.append(origin_point)

            # only create origin point desc,add to ORIGIN_POINT_DICT.
            if (root_sys == "" and sub_sys == "") and point_name != "":
                if point_name not in ORIGIN_POINT_DICT:
                    origin_point = OriginPointDesc(tag_name=point_name, describe=point_desc, unit=g.unit)
                    ORIGIN_POINT_DICT[point_name] = origin_point

        for system in sub_system_dict:
            sub_systems.append(sub_system_dict[system])

        add_all(ORIGIN_POINT_DICT.values())

        add_all(sub_systems)


def add_alias(save_filename, encoding='gb2312'):
    """
    为系统添加别名
    ----------
    Args:
        save_filename: 文件存储的文件地址
    ----------
    Returns:
    """
    try:
        with open(save_filename, 'r', encoding=encoding) as f:
            reader = csv.reader(f)
            rows = [row for row in reader]
            table_length = len(rows)
            table_header = rows[0]
            table_header = [column.replace(" ", "") for column in table_header]
            root_sys_index = table_header.index('大系统')
            sub_sys_index = table_header.index('子系统')
            point_desc_index = table_header.index('系统描述')
            for i in range(1, table_length):
                row_content = rows[i]
                root_sys = row_content[root_sys_index]
                sub_sys = row_content[sub_sys_index]
                system_desc = row_content[point_desc_index]
                # print(f"大系统:{root_sys}, 子系统:{sub_sys}, 系统描述:{system_desc}")
                if sub_sys == "":
                    SystemConfig.set_system_config_alias(system_desc, name=root_sys)
                else:
                    SystemConfig.set_system_config_alias(system_desc, name=sub_sys)
        return True, "添加别名成功"
    except Exception as e:
        return False, str(e)


def get_children_points(system):
    res = []
    if system and not system.children:
        res = system.to_json()['origin_points']
    else:
        for child in system.children.split(','):
            sub_system = SystemConfig.get_by_name(child, g.unit)
            res.extend(get_children_points(sub_system))
    return res


def filter_origin_points(origin_points: List[dict]):
    tag_names = [origin_point["tag_name"] for origin_point in origin_points]
    true_list = OriginPointDesc.get_have_point_desc_points(tag_names)
    return list(filter(lambda x: x['tag_name'] in true_list, origin_points))


def rebuild_origin_point_system_config_map(local_file_path):
    encoding = get_file_encoding(local_file_path)
    save_db(local_file_path, encoding)
    set_redis_system_tree({})
    system_dict.clear()
    sub_system_dict.clear()
    system_children_dict.clear()


def add_alias_from_alias_file(local_file_path):
    set_redis_system_tree({})
    system_dict.clear()
    sub_system_dict.clear()
    system_children_dict.clear()
    encoding = get_file_encoding(local_file_path)
    add_alias(local_file_path, encoding=encoding)
    set_redis_system_tree({})


def clear_table(unit):
    clear_origin_point_system_table(unit)
    SystemConfig.clear_table(unit)
    OriginPointDesc.clear_table(unit)


@sysconfig_blueprint.route("/bulk_add_origin_points", methods=['POST'])
@handle_error
def add_origin_points():
    sysconfig_file = request.files['sysconfig_file']
    alias_file = request.files['alias_file']
    have_clear, data = get_request_data(request, ['clear'])
    if have_clear:
        if data.get('clear', "None").strip() in ("True", "ture"):
            clear_table()

    if sysconfig_file is None or alias_file is None:
        return false_return(f"请上传文件")

    sysconfig_file_allowed, sysconfig_file_filename, sysconfig_file_extension = allowed_upload_csv(sysconfig_file.filename)
    alias_file_allowed, alias_file_filename, alias_file_extension = allowed_upload_csv(alias_file.filename)
    if not (sysconfig_file_allowed and alias_file_allowed):
        error_message = "文件后缀名必须是.csv"
        return false_return(error_message)

    # 存储到本地文件夹中
    sysconfig_path = store_request_file(sysconfig_file, sysconfig_file_filename, prefix="_sysconfig_", suffix="_bulk")
    alias_path = store_request_file(alias_file, alias_file_filename, prefix="_alias_", suffix="_bulk")

    encoding = get_file_encoding(sysconfig_path)
    sysconfig_result, sysconfig_msg = bulk_add_origin_points_from_file(sysconfig_path, encoding)
    # 批量添加成功后，更新redis里的原始点名
    if sysconfig_result:
        write_origin_points_to_redis(origin_point=True, inter_variable=False)
    else:
        return false_return(sysconfig_msg)

    encoding = get_file_encoding(alias_path)
    alias_result, alias_msg = add_alias(alias_path, encoding=encoding)
    if alias_result:
        return true_return("批量添加成功")
    else:
        return false_return(alias_msg)


def bulk_add_origin_points_from_file(local_file_path, encoding='gb2312') -> Tuple[bool, str]:
    def check_nan(num):
        return num != num

    system_point_map: Dict[str, List[str]] = {}
    system_map: Dict[str, SystemConfig] = {}
    origin_point_list = list()
    roots_system_list = []

    index_map = {}
    HEADER = ["大系统", "子系统", "点描述", "点名"]
    try:
        with open(local_file_path, 'r', encoding=encoding) as f:
            data: DataFrame = pd.read_csv(f, encoding=encoding)
            lack_header = set(HEADER) - set([h.strip() for h in data.keys()])
            if len(lack_header) != 0:
                return False, f"文件头格式不正确，正确格式应为:{','.join(HEADER)}.实为：{','.join(data.keys())}, 缺少列：{','.join(lack_header)}"
            else:
                for h in data.keys():
                    if h.strip() in HEADER:
                        index_map[h.strip()] = data[h].tolist()
            root_sys_index = index_map.get('大系统')
            sub_sys_index = index_map.get('子系统')
            point_name_index = index_map.get('点名')
            point_desc_index = index_map.get('点描述')
            for i in range(len(root_sys_index)):
                root_system = None
                sub_system = None
                root_sys = root_sys_index[i] if not check_nan(root_sys_index[i]) else ""
                sub_sys = sub_sys_index[i] if not check_nan(sub_sys_index[i]) else ""
                point_name = point_name_index[i]
                if check_nan(point_name):
                    return False, f"第{i}行: 点名不存在"
                point_desc = point_desc_index[i] if not check_nan(point_desc_index[i]) else ""
                # 如果是大系统
                if root_sys != "":
                    if root_sys not in system_map:
                        root_system = SystemConfig(name=root_sys, parent=None, alias=None, children="", unit=g.unit, DELETED=False)
                        system_map[root_sys] = root_system
                        roots_system_list.append(root_system)
                    else:
                        root_system = system_map[root_sys]

                # 如果是子系统
                if sub_sys != "":
                    if sub_sys not in system_map:
                        sub_system = SystemConfig(name=sub_sys, parent=root_sys, alias=None, children="", DELETED=False, unit=g.unit)
                        system_map[sub_sys] = sub_system
                    else:
                        sub_system = system_map[sub_sys]
                    # 如果sys_system不为空 and root_system为空，则 bug.
                    if root_system is None:
                        return False, f"第{i}行: 小系统存在，大系统不存在!"
                    if sub_sys not in root_system.children:
                        if root_system.children != "":
                            root_system.children = root_system.children + "," + sub_sys
                        else:
                            root_system.children = sub_sys

                origin_point = OriginPointDesc(tag_name=point_name, describe=point_desc, unit=g.unit)
                origin_point_list.append(origin_point)

                # 建立子系统和点的关系
                if sub_system is not None:
                    if sub_sys in system_point_map:
                        system_point_map[sub_sys].append(point_name)
                    else:
                        system_point_map[sub_sys] = [point_name]

            # 对顺序有要求
            # 1.首先插入根节点 2插入子节点 3插入点
            # 首先存储根结点名称，用于后续将根结点从system_map中去除.
            # 原因在于根结点在commit后已经从session中失效，无法再次访问内存对象，所以要去除
            root_sys_name = [sys.name for sys in roots_system_list]
            SystemConfig.upsert(roots_system_list, g.unit)
            for sys in root_sys_name:
                system_map.pop(sys, None)
            SystemConfig.upsert(list(system_map.values()), g.unit)
            if len(origin_point_list) > 0:
                OriginPointDesc.upsert(origin_point_list)
            SystemConfig.batch_add_origin_points_to_systems_list(system_point_map, g.unit)
            write_origin_points_to_redis(origin_point=True, inter_variable=False)
            return True, "导入成功"
    except Exception as e:
        traceback.print_exc()
        return False, str(e)
