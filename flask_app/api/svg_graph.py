from flask import Blueprint, request, g
from flask_app.api import handle_error
from flask_app.common.before_request import get_request_data, check_page, check_unit
from flask_app.common.result import false_return, true_return
from flask_app.common.update import update
from flask_app.models.system_graph import SystemGraph
from flask_app.models.system_graph_point import SystemGraphPoint
from flask_app.models.point_desc import PointDesc


sys_graph_blueprint = Blueprint("sys_graph_blueprint", __name__, url_prefix='/system_graph')


@sys_graph_blueprint.before_request
@handle_error
def before_request():
    check_unit()
    if request.method == 'GET' or request.method == 'DELETE':
        g.data = request.args
    else:
        g.data = request.get_json()


@sys_graph_blueprint.route('', methods=['GET'])
@handle_error
def get_system_graph():
    have_id, data = get_request_data(request, ['gid'])
    if have_id:
        gid = data['gid']
        graph = SystemGraph.get_by_id(gid, g.unit)
        if not graph:
            return false_return('没有找到指定系统图')
        return true_return('查询成功', graph.to_json())
    
    all_graphs, _ = SystemGraph.get_all_in_unit(g.unit)

    return true_return('查询成功', [g.to_json() for g in all_graphs if g])


def check_img(img_file):
    if not img_file:
        return false_return('没有接收到图片')
    try:
        suffix = img_file.filename.split('.')[-1]
        if suffix not in ['jpg', 'png', 'svg', 'jpeg']:
            return False, '不支持的图片格式'
    except:
        return False, '不支持的图片格式'
    
    return True, suffix


@sys_graph_blueprint.route('', methods=['POST'])
@handle_error
def add_new_graph():
    success, data = get_request_data(request, ['graph_name'])
    if not success:
        return false_return(data)
    
    graph_name = data['graph_name']
    existed_graph = SystemGraph.get_by_name(graph_name, g.unit)
    if existed_graph:
        return false_return('系统图名称重复')

    img_file = request.files.get('img_file')
    success, suffix_maybe = check_img(img_file)
    if not success:
        return false_return(suffix_maybe)
    
    save_path = 'static/{}-u{}.{}'.format(graph_name, g.unit, suffix_maybe)
    img_file.save(save_path)
    
    SystemGraph.create(graph_name, save_path, g.unit)
    return true_return('创建成功')


@sys_graph_blueprint.route('', methods=['PUT'])
@handle_error
def modify_graph():
    success, data = get_request_data(request, ['gid'])
    if not success:
        return false_return(data)
    
    gid = data['gid']
    graph = SystemGraph.get_by_id(gid, g.unit)
    if not graph:
        return false_return('没有找到指定系统图')
    
    graph_name = g.data.get('graph_name')
    img_file = g.data.get('img_file')
    success, suffix_maybe = check_img(img_file)
    if success:
        save_path = 'static/{}-u{}.{}'.format(graph_name, g.unit, suffix_maybe)
        img_file.save(save_path)
    
    if graph_name:
        existed_graph = SystemGraph.get_by_name(graph_name, g.unit)
        if existed_graph:
            return false_return('系统图名称重复')
        SystemGraph.update_graph(gid, {'graph_name': graph_name})
    
    return true_return('修改成功')


@sys_graph_blueprint.route('', methods=['DELETE'])
@handle_error
def delete_graph():
    success, data = get_request_data(request, ['gid'])
    if not success:
        return false_return(data)
    
    gid = data['gid']
    graph = SystemGraph.get_by_id(gid, g.unit)
    if not graph:
        return false_return('没有找到指定系统图')
    
    effected_points, _ = SystemGraphPoint.get_all_in_graph(gid)
    gpids = [p.gpid for p in effected_points if p]
    SystemGraphPoint.delete_points(gpids)

    SystemGraph.delete_by_id(gid)
    return true_return('删除成功')


@sys_graph_blueprint.route('/point', methods=['GET'])
@handle_error
def get_graph_point():
    have_gid, data = get_request_data(request, ['gid'])
    if have_gid:
        gid = data['gid']
        target_graph = SystemGraph.get_by_id(gid, g.unit)
        if not target_graph:
            return false_return('找不到指定系统图')
        
        graph_points, _ = SystemGraphPoint.get_all_in_graph(gid)
        return true_return('查询成功', [p.to_json() for p in graph_points if p])
    
    have_pid, data = get_request_data(request, ['gpid'])
    if not have_pid:
        return false_return(data)
    
    gpid = data['gpid']
    target_graph_point = SystemGraphPoint.get_by_id(gpid, g.unit)
    if not target_graph_point:
        return false_return('找不到指定系统图点')
    return true_return('查询成功', target_graph_point.to_json())


@sys_graph_blueprint.route('/point', methods=['POST'])
@handle_error
def add_new_graph_point():
    success, data = get_request_data(request, ['x', 'y', 'graph'])
    if not success:
        return false_return(data)
    
    x = data['x']
    y = data['y']
    gid = int(data['graph'])
    target_graph = SystemGraph.get_by_id(gid, g.unit)
    if not target_graph:
        return false_return('找不到指定系统图')
    
    point = g.data.get('point')
    if point:
        target_point = PointDesc.get_by_id(point, g.unit)
        if not target_point:
            return false_return('找不到指定点')

    SystemGraphPoint.create(x, y, g.unit, gid, point)
    return true_return('创建成功')


@sys_graph_blueprint.route('/point', methods=['PUT'])
@handle_error
def modify_graph_point():
    success, data = get_request_data(request, ['gpid'])
    if not success:
        return false_return(data)
    
    gpid = data['gpid']
    target_point = SystemGraphPoint.get_by_id(gpid, g.unit)
    if not target_point:
        return false_return('找不到指定系统图点')

    update_data = update(g.data, ['x', 'y', 'point'])
    SystemGraphPoint.update_point(gpid, update_data)
    return true_return('修改成功')


@sys_graph_blueprint.route('/point', methods=['DELETE'])
@handle_error
def delete_graph_point():
    success, data = get_request_data(request, ['gpid'])
    if not success:
        return false_return(data)
    
    gpid = data['gpid']
    target_point = SystemGraphPoint.get_by_id(gpid, g.unit)
    if not target_point:
        return false_return('找不到指定系统图点')

    SystemGraphPoint.delete_by_id(gpid)
    return true_return('删除成功')
