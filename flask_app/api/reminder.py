import json
from flask import Blueprint, g, request
from flask_app.api import handle_error
from flask_app.common.before_request import get_border, get_request_data, check_unit
from flask_app.common.result import false_return, true_return
from flask_app.util.token_auth import auth
from flask_app.models.reminder import Reminder
from flask_app import redis

reminder_blueprint = Blueprint("reminder_blueprint", __name__, url_prefix='/reminder')


@reminder_blueprint.before_request
@handle_error
def before_request():
    success, msg = check_unit()
    if not success:
        return false_return(msg)
    if request.method == 'GET' or request.method == 'DELETE':
        g.data = request.args
    else:
        g.data = request.get_json()


@reminder_blueprint.route('/filter', methods=['GET'])
@handle_error
def filter_reminders():
    mid = g.data.get('mid', None)
    version = g.data.get('version', None)
    pid = g.data.get('pid', None)
    rtype = g.data.get('rtype', None)
    model_name = g.data.get('model_name', None)
    point_name = g.data.get('point_name', None)
    state = g.data.get('state', None)

    page = g.data.get('page', None)
    size = g.data.get('size', None)
    if page:
        page = int(page)
    if size:
        size = int(size)

    reminders, total = Reminder.search(mid, version, pid, rtype, model_name, point_name, state, g.unit, page, size)
    
    result = {
        'total': total,
        'reminders': [reminder.to_json() for reminder in reminders]
    }
    return true_return("查询成功", result)


@reminder_blueprint.route('', methods=['GET'])
@handle_error
def query_reminders():
    have_id, data = get_request_data(request, ['rid'])
    if have_id:
        rid = data['rid']
        reminder = Reminder.get_by_id(rid, g.unit)
        if not reminder:
            return false_return("通知不存在")
        return true_return("查询成功", reminder.to_json())

    have_page, _, _ = get_border(request)
    if have_page:
        page = int(g.data.get('page'))
        size = int(g.data.get('size'))
        reminders, total = Reminder.get_in_unit_by_pages(g.unit, page, size)
    else:
        reminders, total = Reminder.get_all_in_unit(g.unit)
    result = {
        'total': total,
        'reminders': [reminder.to_json() for reminder in reminders]
    }
    return true_return("查询成功", result)


@reminder_blueprint.route('', methods=['PUT'])
@auth.login_required
@handle_error
def modify_reminder():
    success, data = get_request_data(request, ['rid'])
    if not success:
        return false_return('缺少rid')
    
    if 'state' not in data and 'remark' not in data:
        return false_return('找不到可更新的内容', data)
    
    if data['state'] < 0 or data['state'] > 2:
        return false_return("非法state'{}'".format(data['state']))
    
    rid = data['rid']
    target_reminder = Reminder.get_by_id(rid, g.unit)
    if not target_reminder:
        return false_return('通知{}不存在'.format(rid))

    if 'state' in data:
        Reminder.update_state(rid, g.unit, g.user.uid, data['state'])
    
    if 'remark' in data:
        Reminder.update_reminder(rid, {'remark': data['remark']})
    
    return true_return('更新成功', rid)


@reminder_blueprint.route('', methods=['DELETE'])
@handle_error
def delete_reminder():
    success, data = get_request_data(request, ['rid'])
    if not success:
        return false_return('缺少rid')
    rid = data['rid']
    target_reminder = Reminder.get_by_id(rid, g.unit)
    if not target_reminder:
        return false_return('找不到指定预警通知')

    Reminder.delete_reminder(rid)

    return true_return('删除成功通知{}'.format(rid))


@reminder_blueprint.route('/test', methods=['POST'])
@handle_error
def test_multi_create():
    success, data = get_request_data(request, ['data'], ['data'])
    if not success:
        return false_return(data)
    
    create_args = data['data']
    print(create_args)
    print(type(create_args))
    Reminder.create_reminders(create_args)

    return true_return('成功创建')


@reminder_blueprint.route('/clear', methods=['DELETE'])
@handle_error
@auth.login_required
def clear_reminder():
    success, info = Reminder.clear()
    if not success:
        return false_return(info)
    
    return true_return(info)


@reminder_blueprint.route('/realtime_reminder', methods=['GET'])
@handle_error
@auth.login_required
def realtime_reminder():
    success, msg = check_unit()
    if not success:
        return false_return(msg)
    realtime = json.loads(redis.read("realtime_warning"))
    unit_realtime_reminder = list()
    for realtime_warning in realtime:
        if int(realtime_warning['unit']) == int(g.unit):
            unit_realtime_reminder.append(realtime_warning)
    return true_return("查询成功", {'realtime_warning':unit_realtime_reminder})