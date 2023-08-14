from flask import Blueprint, request, g
from flask_app.common.before_request import get_request_data, check_page
from flask_app.common.result import false_return, true_return
from flask_app.common.update import update
from flask_app.models.sub_system import SubSystem

subsys_blueprint = Blueprint("subsys_blueprint", __name__, url_prefix='/subsys')


@subsys_blueprint.route('', methods=['POST'])
def create_system():
    success, data = get_request_data(request, ['name'], ['member'])
    if not success:
        return false_return(data)
    name = data['name']
    member = data['member']
    system = SubSystem.create_system(name, member, g.unit)
    if success:
        return true_return("创建成功", system.to_json())


@subsys_blueprint.route('', methods=['DELETE'])
def delete_system():
    success, data = get_request_data(request, ['sid'])
    if not success:
        return false_return(data)
    sid = data['sid']
    system = SubSystem.get_by_id(sid)
    if not system:
        return false_return("子系统不存在")
    SubSystem.delete_system(sid)
    return true_return("删除成功", sid)


@subsys_blueprint.route('', methods=['PUT'])
def update_system():
    success, data = get_request_data(request, ['sid'], ['member'])
    if not success:
        return false_return(data)
    sid = data['sid']
    system = SubSystem.get_by_id(sid)
    if not system:
        return false_return("子系统不存在")
    result = update(data, ['name', 'member'])
    success = SubSystem.update_system(sid, result)
    if success:
        return true_return("更新成功", sid)
    return false_return("未修改任何参数")


@subsys_blueprint.route('', methods=['GET'])
def get_system():
    have_sid, data = get_request_data(request, ['sid'])
    if not have_sid:
        _, page, size = check_page(request)
        systems, total = SubSystem.get_by_unit(g.unit, page, size)
        
        res = {
            'sub_systems': [system.to_json() for system in systems],
            'total': total
        }
        return true_return("查询成功", res)
    
    sid = data['sid']
    system = SubSystem.get_by_id(sid)
    if not system:
        return false_return("子系统不存在")
    return true_return("查询成功", system.to_json())
