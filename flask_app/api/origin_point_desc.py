import traceback
import io
import datetime

from flask import Blueprint, g, make_response, request, send_file
from flask_app.util.file_util import store_request_file
from flask_app.api import handle_error
from flask_app.common.before_request import get_border, get_request_data, check_unit
from flask_app.common.result import false_return, true_return
from pandas import DataFrame
from flask_app.models.system_config import SystemConfig
from flask_app.util.common.file_os import *
from flask_app.models.origin_point_dec import OriginPointDesc, PointType, write_origin_points_to_redis
from flask_app.models.point_desc import PointDesc
from flask_app.models.relation_map import add_all
from flask_app.util.file_util import get_file_encoding
from flask_app.util.str_util import to_bool

origin_point_blueprint = Blueprint("origin_point_blueprint", __name__, url_prefix='/originpoint')


@origin_point_blueprint.before_request
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


@origin_point_blueprint.route('/upload_file', methods=['POST'])
@handle_error
def upload_file():
    try:
        tags_desc_file = request.files['points_file']
        if tags_desc_file:
            allowed, filename, extension = allowed_upload_csv(tags_desc_file.filename)
            if not allowed:
                error_message = "文件后缀名必须是.csv"
                return false_return(error_message)
            path = store_request_file(tags_desc_file, filename, prefix="_origin_pointdesc")
            print(filename, extension)
            encoding = get_file_encoding(path)
            PointDesc.clear_table(g.unit)
            batch_create_point_desc_by_file(path, encoding)
            write_origin_points_to_redis(origin_point=True, inter_variable=False)
            return true_return("文件上传成功")
        return false_return("请选择文件")
    except UnicodeDecodeError as decode_error:
        traceback.print_exc()
        return false_return('文件编码错误,无法解析,文件编码格式应为UTF-8 或 GBK 或 GB2312')
    except Exception as e:
        traceback.print_exc()
        return false_return('csv文件中需要有name和desc列, 文件编码(encoding) 需要为UTF-8 或 GBK 或 GB2312 ')


def batch_create_point_desc_by_file(file, encoding='utf-8', check=True):
    points = []
    point_name_set = set()
    data: DataFrame = pd.read_csv(file, encoding=encoding)

    point_name_list = data['点名'].tolist()
    point_desc_list = data['点描述 '].tolist()
    upper_limit_list = data['上上限H'].tolist()
    lower_limit_list = data['下下限L'].tolist()
    expect_list = data['期望值'].tolist()
    offset_list = data['D//-D'].tolist()
    switch_list = data['触发标签'].tolist()
    variance_duration_list = data['坏点时间'].tolist()
    actual_list = data['实际值'].tolist()
    # 事前校验？
    # 校验
    if check:
        result = PointDesc.check_point_name_list(point_name_list)

        def check_point_name(point_name, point_names):
            return point_name in point_names

        valid_point_name_index = []
        for index, point_name in enumerate(point_name_list):
            point_name = point_name.strip()
            if check_point_name(point_name, result):
                valid_point_name_index.append(index)
    else:
        valid_point_name_index = list(range(len(point_name_list)))

    def check_nan(num):
        return num != num

    for row_index in valid_point_name_index:
        point_name = point_name_list[row_index]
        point_name = point_name.strip()
        if point_name in point_name_set:
            continue
        else:
            point_name_set.add(point_name)
        point_desc = point_desc_list[row_index]
        upper_limit = upper_limit_list[row_index] if not check_nan(upper_limit_list[row_index]) else None
        lower_limit = lower_limit_list[row_index] if not check_nan(lower_limit_list[row_index]) else None
        offset = offset_list[row_index] if not check_nan(offset_list[row_index]) else None
        expect = expect_list[row_index] if not check_nan(expect_list[row_index]) else None
        switch = switch_list[row_index] if not check_nan(switch_list[row_index]) else None
        variance_duration = variance_duration_list[row_index] if not check_nan(variance_duration_list[row_index]) else None
        actual = actual_list[row_index] if not check_nan(actual_list[row_index]) else None
        variance_gate = None
        point = PointDesc(point_name=point_name, describe=point_desc, upper_limit=upper_limit, lower_limit=lower_limit,
                          expect=expect, offset=offset, switch=switch, variance_duration=variance_duration,
                          variance_gate=variance_gate, actual=actual, unit=g.unit)
        points.append(point)

    add_all(points)


@origin_point_blueprint.route('/origin_point', methods=['POST'])
@handle_error
def add_origin_point_desc():
    success, data = get_request_data(request, ['tag_name', 'describe'])
    if not success:
        return false_return(data)
    tag_name = data['tag_name']
    describe = data['describe']
    tag_name = tag_name.strip()
    origin_point = OriginPointDesc.get_by_name(tag_name, g.unit)
    if origin_point is not None:
        return false_return("点名重复")
    else:
        origin_point = OriginPointDesc.create_origin_point_desc(tag_name=tag_name, describe=describe, unit=g.unit)
        write_origin_points_to_redis(origin_point=True, inter_variable=False)
        return true_return("创建成功", origin_point.to_json())


@origin_point_blueprint.route('/origin_point', methods=['GET'])
@handle_error
def query_origin_point_desc():
    """
    查询单个点或某个系统所属点的信息
    ----------
    Args:
        tag_name: 点名
        cid: 系统id
    ----------
    Returns:
        OriginPointDesc: 点描述对象（单个对象或列表）
    """
    have_tag_name, data = get_request_data(request, ['tag_name'])
    if have_tag_name:
        tag_name = data['tag_name']
        origin_point = OriginPointDesc.get_by_name(tag_name, g.unit)
        if origin_point:
            return true_return("查询成功", origin_point.to_json())
        else:
            return true_return("查询成功", None)

    have_cid, data = get_request_data(request, ['cid'])
    if have_cid:
        cid = data['cid']
        system = SystemConfig.get_by_id(cid, g.unit)
        if not system:
            return false_return('找不到指定系统cid-{}'.format(cid))
        origin_points = get_children_points(system)
        res = {
            "system_config": system.to_json(full=False),
            "origin_points": origin_points
        }
        return true_return("ok", res)
    return false_return("缺少tag_name，cid")


def get_children_points(system):
    res = []
    if system and not system.children:
        res = system.to_json()['origin_points']
    else:
        for child in system.children.split(','):
            sub_system = SystemConfig.get_by_name(child, g.unit)
            res.extend(get_children_points(sub_system))
    return res


@origin_point_blueprint.route('/origin_point', methods=['DELETE'])
@handle_error
def remove_origin_point_desc():
    success, data = get_request_data(request, ['tag_name'])
    if not success:
        return false_return(data)
    tag_name = data['tag_name']
    origin_point = OriginPointDesc.delete_origin_point(tag_name, g.unit)
    write_origin_points_to_redis(origin_point=True, inter_variable=False)
    return true_return("删除成功", origin_point)


@origin_point_blueprint.route('/origin_point', methods=['PUT'])
@handle_error
def modify_origin_point_desc():
    success, data = get_request_data(request, ['tag_name', 'describe'])
    if not success:
        return false_return(data)
    tag_name = data['tag_name']
    describe = data['describe']
    tag_name = tag_name.strip()
    origin_point = OriginPointDesc.set_desc(tag_name, describe, g.unit)
    return true_return("修改成功", origin_point)


@origin_point_blueprint.route('/systems_belong', methods=['POST'])
@handle_error
def add_systems_to_origin_point():
    success, data = get_request_data(request, ['tag_name', 'systems'], ['systems'])
    if not success:
        return false_return(data)
    tag_name = data['tag_name']
    systems = data['systems']
    tag_name = tag_name.strip()
    msg = OriginPointDesc.add_systems(tag_name, systems, g.unit)
    return true_return(msg)


@origin_point_blueprint.route('/systems_belong', methods=['DELETE'])
@handle_error
def remove_systems_to_origin_point():
    success, data = get_request_data(request, ['tag_name', 'system'])
    if not success:
        return false_return(data)
    tag_name = data['tag_name']
    systems = data['system']
    msg = OriginPointDesc.delete_systems(tag_name, systems, g.unit)
    return true_return(msg)


@origin_point_blueprint.route('/points', methods=['GET'])
@handle_error
def get_all_origin_points_in_unit():
    success, data = get_request_data(request, ['page', 'size'])
    if success:
        page = int(data.get('page', 1))
        size = int(data.get('size', 40))
        origin_point_list, total = OriginPointDesc.get_all_in_unit(g.unit, page, size)
    else:
        origin_point_list, total = OriginPointDesc.get_all_in_unit(g.unit)
    result = {
        'total': total,
        'origin_points': [p.to_json(full=True) for p in origin_point_list]
    }
    return true_return("查询成功", result)


@origin_point_blueprint.route("/points", methods=['DELETE'])
@handle_error
def delete_origin_points():
    success, data = get_request_data(request, ['tag_names'], ['tag_names'])
    if not success:
        return false_return(data)
    tag_names = data['tag_names']
    print(tag_names)
    OriginPointDesc.delete_origin_points(tag_names, g.unit)
    return true_return("删除成功")


@origin_point_blueprint.route('/multi_search', methods=['GET'])
def multi_search():
    """
    多条件查询点名信息
    ----------
    Args:
        tag_name: 点名
        point_desc: 点描述
        system: 系统名
        system_alias: 系统别名
    ----------
    Returns:
        points: 点描述对象（列表）
    """
    _, page, size = check_page(request)

    point_name = g.data.get('tag_name')
    point_desc = g.data.get("point_desc")
    system = g.data.get('system')
    system_alias = g.data.get('system_alias')

    selected_points, total = OriginPointDesc.search_all(point_name, point_desc, system, system_alias, g.unit, page, size)

    res = {
        'origin_points': [p.to_json() for p in selected_points],
        'total': total
    }

    return true_return('筛选成功', res)


def check_page(req: request):
    """检擦request中是否含有分页信息
    """
    try:
        page = int(req.args['page'])
        size = int(req.args['size'])
    except KeyError:
        return False, None, None
    return True, page, size


@origin_point_blueprint.route('/download', methods=['GET'])
@handle_error
def download_file():
    # _, page, size = check_page(request)

    tag_name = g.data.get('tag_name', None)
    point_desc = g.data.get("point_desc", None)
    sys_name = g.data.get('system', None)
    sys_alias = g.data.get('system_alias', None)
    all_unit = g.data.get('all_unit', False)
    
    all_unit = to_bool(all_unit)
    
    return_points, size = OriginPointDesc.search_all_no_page(tag_name, point_desc, sys_name, sys_alias, g.unit, 
                                                             point_type=[PointType.ORIGINPOINTDESC.value], all_unit=all_unit)

    if size:
        out = io.BytesIO()
        filename = str(datetime.date.today()) + 'origin_point_download' + '.csv'
        return_points = format_data(return_points)
        return_points = pd.DataFrame(return_points)
        return_points.to_csv(out, index=False)
        
        out.seek(0)
        # return send_file(out, mimetype='text/csv', as_attachment=True, attachment_filename=filename)
        
        response = make_response(out.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Content-Disposition'] = 'attachment; filename=' + filename
        return response
    else:
        return false_return("no data", None)


def format_data(data: list) -> dict:
    return_points = {
        '英文点名': [],
        '中文点名': [],
        '对应系统名': []
    }
    for point in data:
        return_points['英文点名'].append(point.tag_name)
        return_points['中文点名'].append(point.describe)
        if point.systems:
            return_points['对应系统名'].append(' '.join([sys.name for sys in point.systems]))
        else:
            return_points['对应系统名'].append('')
    return return_points


# service
# def query_origin_point_bytag(tag_name: str):
    
#     """ 
#     query a simgle origin point by tag_name
#     """
#     return OriginPointDesc.get_by_name(tag_name, g.unit)


# def query_origin_point_bycid(cid: str):
#     """ 
#     query a series of origin points belongs to a cid
#     """
#     system = SystemConfig.get_by_id(cid, g.unit)
#     if not system:
#         return None
    