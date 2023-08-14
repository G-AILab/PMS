from flask import Blueprint, request, g
from flask_app.common.before_request import get_request_data
from flask_app.common.result import false_return, true_return
from flask_app.models.user import User
from flask_app.models.role import Role
from flask_app.api import handle_error
from flask_app.common.before_request import get_request_data, get_border
from flask_app.util.token_auth import auth

user_blueprint = Blueprint("user_blueprint", __name__, url_prefix='/user')

@user_blueprint.before_request
@handle_error
def before_request():
    if request.method == 'GET' or request.method == 'DELETE':
        g.data = request.args
        return 
    if request.content_type == 'application/json':
        g.data = request.get_json()

@user_blueprint.route('', methods=['POST'])
def login():
    success, user = verify_user(request)
    if not success:
        return false_return(user)
    return true_return("登录成功", user.to_json())

@user_blueprint.route('/filter', methods=['GET'])
@handle_error
def filter_users():
    uid = g.data.get('uid', None)
    username =g.data.get('username', None)
    email =g.data.get('email', None)
    prediction =g.data.get('prediction', None)
    fields =g.data.get('fields', None)
    role_id =g.data.get('role_id', None)

    have_page, left, right = get_border(request)
    if have_page:
        users, total = User.search_by_pages(uid,username, email, prediction, fields, role_id, left, right)
    else:
        users, total = User.search(uid,username, email, prediction, fields, role_id)
    
    result = {
        'total': total,
        'users': [user.to_json() for user in users]
    }
    return true_return("查询成功", result)

@user_blueprint.route('', methods=['GET'])
@handle_error
# @auth.login_required
def query_users():
    have_id, data = get_request_data(request, ['uid'])
    if have_id:
        uid = data['uid']
        user = User.get_by_id(uid)
        if not user:
            return false_return("用户不存在")
        return true_return("查询成功", user.to_json())

    have_page, left, right = get_border(request) # page , se
    if have_page:
        users, total = User.get_by_pages(left, right)
    else:
        users, total = User.get_all()
    result = {
        'total': total,
        'users': [user.to_json() for user in users]
    }
    return true_return("查询成功", result)


@user_blueprint.route('', methods=['PUT'])
def register():
    success, data = get_request_data(request, ['username', 'password', 'role_id','email'])
    if not success:
        return false_return(data)
    username = data['username']
    password = data['password']
    role_id = data['role_id']
    role = Role.get_by_id(role_id)
    if role == None:
        return false_return(f'角色: {role_id} 不存在')
    email = data['email']
    user = User.get_by_username(username)
    if user:
        return false_return("用户名已存在")
    user = User.add_user(username, password, email, role_id)
    return true_return("注册成功", user.to_json())


@user_blueprint.route('', methods=['DELETE'])
def delete_user():
    success, data = get_request_data(request, ['username'])
    if not success:
        return false_return(data)
    username = data['username']
    user = User.get_by_username(username)
    User.delete_user(user.username)
    return true_return("删除成功", user.to_json())


@user_blueprint.route('/set_prediction', methods=['POST'])
def set_prediction():
    success, data = get_request_data(request, ['uid'], ['prediction'])
    if not success:
        return false_return(data)
    uid = data['uid']
    user = User.get_by_id(uid)
    if not user:
        return false_return("用户不存在")
    prediction = data['prediction']
    if len(prediction) != 4:
        return false_return("实时预测必须是4个字段")
    User.set_prediction(uid, prediction)
    return true_return("实时预测字段设置成功", prediction)


@user_blueprint.route('/set_detection', methods=['POST'])
def set_detection():
    success, data = get_request_data(request, ['uid'], ['detection'])
    if not success:
        return false_return(data)
    uid = data['uid']
    user = User.get_by_id(uid)
    if not user:
        return false_return("用户不存在")
    detection = data['detection']
    if len(detection) != 4:
        return false_return("异常检测必须是4个字段")
    User.set_detection(uid, detection)
    return true_return("异常检测字段设置成功", detection)


@user_blueprint.route('/set_fields', methods=['POST'])
def set_fields():
    success, data = get_request_data(request, ['uid'], ['fields'])
    if not success:
        return false_return(data)
    uid = data['uid']
    user = User.get_by_id(uid)
    if not user:
        return false_return("用户不存在")
    fields = data['fields']
    User.set_fields(uid, fields)
    return true_return("点名设置成功", fields)


@user_blueprint.route('/set_redis_time', methods=['POST'])
def set_redis_time():
    success, data = get_request_data(request, ['uid', 'redis_time'])
    if not success:
        return false_return(data)
    uid = data['uid']
    user = User.get_by_id(uid)
    if not user:
        return false_return("用户不存在")
    redis_time = data['redis_time']
    User.set_redis_time(uid, redis_time)
    return true_return("redis秒数设置成功", redis_time)

@user_blueprint.route('/set_role', methods=['POST'])
def set_role():
    success, data = get_request_data(request, ['uid', 'role_id'])
    if not success:
        return false_return(data)
    uid = data['uid']
    role_id = data['role_id']
    role = Role.get_by_id(role_id)
    if role == None:
        false_return("角色不存在")
    user = User.get_by_id(uid)
    if not user:
        return false_return("用户不存在")
    User.set_role(uid, role_id)
    return true_return("用户角色设置成功", role_id)

def verify_user(req):
    success, data = get_request_data(req, ['username', 'password'])
    if not success:
        return False, data
    username = data['username']
    password = str(data['password'])
    user = User.get_by_username(username)
    if not user:
        return False, "用户不存在"
    if password != user.password:
        return False, "密码错误"
    return True, user
