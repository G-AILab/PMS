from flask import Blueprint, request, g
from flask_app.common.before_request import get_request_data
from flask_app.common.result import false_return, true_return
from flask_app.models.role import Role
from flask_app.api import handle_error
from flask_app.common.before_request import get_request_data, get_border

import json
role_blueprint = Blueprint("role_blueprint", __name__, url_prefix='/role')


@role_blueprint.before_request
@handle_error
def before_request():
    if request.method == 'GET' or request.method == 'DELETE':
        g.data = request.args
    else:
        g.data = request.get_json()


@role_blueprint.route('', methods=['PUT'])
def create_role():
    success, data = get_request_data(request, ['name', 'systems'],['systems'])
    if not success:
        return false_return(data)
    name = data['name']
    systems = data['systems']
    role = Role.get_by_name(name)
    if role:
        return false_return("角色已存在，名称重复")
    role = Role.add_role(name, systems)
    return true_return("角色添加成功", role.to_json())

@role_blueprint.route('/set_name', methods=['POST'])
def set_name():
    success, data = get_request_data(request, ['id', 'name'])
    if not success:
        return false_return(data)
    rid = data['id']
    role = Role.get_by_id(rid)
    if not role:
        return false_return("角色不存在")
    name = data['name']
    Role.set_name(rid, name)
    return true_return("name设置成功", name)

@role_blueprint.route('/set_systems', methods=['POST'])
def set_systems():
    success, data = get_request_data(request, ['id'], ['systems'])
    if not success:
        return false_return(data)
    rid = data['id']
    role = Role.get_by_id(rid)
    if not role:
        return false_return("角色不存在")
    systems = data['systems']
    Role.set_systems(rid, systems)
    return true_return("systems设置成功", systems)

@role_blueprint.route('', methods=['GET'])
@handle_error
# @auth.login_required
def query_roles():
    have_id, data = get_request_data(request, ['id'])
    if have_id:
        id = data['id']
        role = Role.get_by_id(id)
        if not role:
            return false_return("角色不存在")
        return true_return("查询成功", role.to_json())

    have_page, left, right = get_border(request) # page , se
    if have_page:
        roles, total = Role.get_by_pages(left, right)
    else:
        roles, total = Role.get_all()
    result = {
        'total': total,
        'roles': [role.to_json() for role in roles]
    }
    return true_return("查询成功", result)


@role_blueprint.route('', methods=['DELETE'])
def delete_role():
    have_id, data = get_request_data(request, ['id'])
    if have_id:
        id = data['id']
        role = Role.get_by_id(id)
        if not role:
            return false_return("角色不存在")
    Role.delete_role(role.id)
    return true_return("删除成功", role.to_json())