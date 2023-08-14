from flask import Blueprint, request, g, current_app
from flask_app.common.result import false_return, true_return
from flask_app.models.user import User
from .user import verify_user
from flask_app.common.before_request import get_request_data, get_border
from authlib.jose import jwt, JoseError

token_blueprint = Blueprint("token_blueprint", __name__, url_prefix='/token')

__author__ = '叶伟伟'


@token_blueprint.route('', methods=['POST'])
def get_token():
    # 拿到数据验证用户
    success, user = verify_user(request)
    if not success:
        return false_return(user)

    # Token
    expiration = current_app.config['TOKEN_EXPIRATION']
    token = generate_auth_token(user.uid,
                                user.username,
                                user.role_id,
                                expiration)
    t = {
        'token': token.decode('ascii')
    }
    return true_return("token生成成功", t)

@token_blueprint.route('/secret', methods=['POST'])
def get_token_info():
    """获取令牌信息"""
    success, data = get_request_data(request, ['token'])

    token = data['token']
    if not success:
        return false_return(data)

    key = current_app.config['SECRET_KEY']
    try:
        data=jwt.decode(token, key)
    except JoseError:
        return false_return("令牌验证失败，重新登录")
    target_user = User.get_by_id(data['uid'])

    return true_return('获取令牌信息成功', target_user.to_json())

def generate_auth_token(uid, username, role_id,expiration=7200,**kwargs):
    """生成令牌"""
    header = {'alg': 'HS256'}
    # 用于签名的密钥
    key = current_app.config['SECRET_KEY']
    # 待签名的数据负载
    data = {
        'uid': uid,
        'username': username,
        'role_id': role_id
    }
    data.update(**kwargs)

    return jwt.encode(header=header, payload=data, key=key)
