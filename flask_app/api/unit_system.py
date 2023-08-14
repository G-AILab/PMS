from flask import Blueprint, g, request
from flask_app.api import handle_error
from flask_app.common.before_request import get_request_data, check_page
from flask_app.common.result import false_return, true_return
from flask_app.models.unit_system import UnitSystem
from flask_app.models.reminder import Reminder
from flask_app.models.model import Model


unit_system_blueprint = Blueprint("unit_system_blueprint", __name__, url_prefix='/unit')


@unit_system_blueprint.before_request
@handle_error
def before_request():
    if request.method == 'GET' or request.method == 'DELETE':
        g.data = request.args
    else:
        g.data = request.get_json()


@unit_system_blueprint.route('', methods=['GET'])
def get_unit():
    have_id, data = get_request_data(request, ['usid'])
    if not have_id:
        have_page, page, size = check_page(request)

        if have_page:
            units, total = UnitSystem.get_by_page(page, size)
        else:
            units, total = UnitSystem.get_all()
        units_json = [u.to_json() for u in units]

        day_diff = int(g.data.get('duration', 4))

        unit_model_statistic = Model.statistic_status_all_units()
        for unit in units_json:
            n_reminders_per_day = Reminder.get_unit_counts_by_days(unit['usid'], day_diff)
            unit['reminders_per_day'] = n_reminders_per_day
            unit['model_statistic'] = unit_model_statistic[unit['usid']]
        
        res = {
            'units': units_json,
            'total': total
        }

        return true_return('查询成功', res)
    
    usid = data['usid']
    units = UnitSystem.get_by_id(usid)
    if units is None:
        return false_return('找不到指定unit')
    
    return true_return('查询成功', units.to_json())


@unit_system_blueprint.route('', methods=['POST'])
def add_unit():
    success, data = get_request_data(request, ['name', 'alias'])
    if not success:
        return false_return(data)
    
    unit_name = data['name']
    unit_alias = data['alias']
    unit_prefix = data.get('prefix', None)

    UnitSystem.create_unit(unit_name, unit_alias, unit_prefix)
    return true_return('新增unit成功')


@unit_system_blueprint.route('', methods=['PUT'])
def modify_unit():
    success, data = get_request_data(request, ['usid'])
    if not success:
        return false_return(data)
    
    usid = data['usid']
    tmp = UnitSystem.get_by_id(usid)
    if tmp is None:
        return false_return('找不到指定unit')

    update_data = dict()
    if 'name' in data:
        update_data['name'] = data['name']
    if 'alias' in data:
        update_data['alias'] = data['alias']
    if 'prefix' in data:
        update_data['prefix'] = data['prefix']
    
    UnitSystem.update_unit(usid, update_data)
    return true_return('更新成功')


@unit_system_blueprint.route('', methods=['DELETE'])
def delete_unit():
    success, data = get_request_data(request, ['usid'])
    if not success:
        return false_return(data)
    
    usid = data['usid']
    tmp = UnitSystem.get_by_id(usid)
    if tmp is None:
        return false_return('找不到指定unit')
    
    UnitSystem.delete_unit(usid)
    tmp = UnitSystem.get_by_id(usid)
    if tmp is not None:
        return false_return('删除失败')
    
    return true_return('删除成功')
