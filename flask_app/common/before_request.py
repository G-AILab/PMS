from flask import request, current_app, g
from flask_app.api import handle_error
from flask_app.common.result import false_return
from werkzeug.datastructures import ImmutableMultiDict

def check_unit():
    if 'unit' not in request.headers:
        return False, '缺少unit'
    g.unit = request.headers.get('unit')
    return True, ''


def get_request_data(req: request, required_fields, list_fields=None):
    """判断request中是否含有required_fields字段，判断request的list_fields字段是否为List
    """
    if list_fields is None:
        list_fields = []
    if req.method == 'GET' or req.method == 'DELETE':
        data = req.args
    else:
        try:
            data = req.get_json()
        except:
            data = req.form
        if not data:
            data = req.form
    result = ImmutableMultiDict(data).to_dict()
    missing_fields = []
    for field in required_fields:
        try:
            data[field]
        except KeyError:
            missing_fields.append(field)
    for field in list_fields:
        try:
            # MultiDict（一键多值字典）对象获取相同key对应的所有的value
            result[field] = data.getlist(field)
        except AttributeError:
            list_data = data.get(field, [])
            if isinstance(list_data, str):
                return False, field + "应该传入一个数组"
            result[field] = list_data
    if len(missing_fields):
        return False, str(missing_fields) + "未填写"
    return True, dict(result)


def get_border(req: request):
    try:
        page = int(req.args['page'])
        size = int(req.args['size'])
    except KeyError:
        return False, -1, -1
    return True, page * size - size, page * size


def check_page(req: request):
    """检擦request中是否含有分页信息
    """
    try:
        page = int(req.args['page'])
        size = int(req.args['size'])
    except KeyError:
        return False, None, None
    return True, page, size
