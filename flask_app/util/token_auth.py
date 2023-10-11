from collections import namedtuple

from authlib.jose import jwt, JoseError
from flask import current_app, g
from flask_httpauth import HTTPTokenAuth

from flask_app.common.result import false_return

auth = HTTPTokenAuth(scheme='JWT')
User = namedtuple('User', ['uid', 'username', 'role_id'])


@auth.verify_token
def verify_token(token):
    """
    请求时带上参数头 TODO
    headers['Authorization'] = 'Bearer ' + token
    """
    User = namedtuple('User', ['uid', 'username', 'role_id'])
    user=User('1', 'admin', '2')
    g.user = user
    # key = current_app.config['SECRET_KEY']
    # try:
    #     jwt.decode(token, key)
    # except JoseError:
    #     return False
    return True


@auth.error_handler
def unauthorized():
    return false_return('未进行token鉴权')





