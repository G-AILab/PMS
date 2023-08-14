import json
import logging
import time
from logging.handlers import TimedRotatingFileHandler

import hd.evaluation
from flask_app.apschedule_tasks import _get_config, result_redis
from flask_app.apschedule_tasks import app as flask_app
from flask_app.models.model import Model
from flask_app.models.reminder import Reminder
from flask_app.common.send_websocket_msg import send_websocket_msg


logger = logging.getLogger('realtime_eval')

# file_handler = logging.FileHandler('logs/realtime_eval.log', mode='w')
file_handler = TimedRotatingFileHandler('logs/realtime_eval.log', when='H', backupCount=4, encoding='utf-8')
file_handler.setLevel(logging.DEBUG if _get_config.DEBUG else logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s")
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)

CYCLE_TIME = _get_config.REALTIME_EVAL_CYCLE  # 实时评估任务循环间隔
EXPIRE_TIME = _get_config.REALTIME_EVAL_EXTIME  # 实时评估结果过期时间
MIN_EVAL_RESULTS = _get_config.MIN_EVAL_RESULTS  # 进行预警判断的最小评估结果个数


def realtime_eval_task():
    print('[{}] realtime_eval_task'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())))
    logger.info('realtime_eval task start!')
    # models_list = result_redis.read('models_list')
    # if not models_list:
    #     models_in_db = list()
    #     with flask_app.app_context():
    #         models = Model.get_all_running_models()
    #     if models:
    #         for model in models:
    #             if model.category != 'detection' and model.evaluate_results is not None:
    #                 models_in_db.append((model.mid, model.version, model.unit))
    #     result_redis.write('models_list', str(models_in_db), expire=EXPIRE_TIME)
    #     models_list = models_in_db
    #     logger.debug('find {} models running'.format(len(models_in_db)))
    # else:
    #     models_list = eval(models_list)
    #     logger.debug('find {} models in "models_list"'.format(len(models_list)))

    reminder_list = list()
    model_updates = list()
    # for model_mid, model_version, model_unit in models_list:
    #     with flask_app.app_context():
    #         model = Model.get_by_id_and_version(model_mid, model_version, model_unit)
    with flask_app.app_context():
        running_models = Model.get_all_running_models()
    if not running_models:
        return
    
    for model in running_models:
        if model.category == 'detection' or not model.evaluate_results:
            continue

        model_mid, model_version = model.mid, model.version
        ts = int(time.time())
        eval_res = evaluate_model(model.category, model.yname, ts, duration=CYCLE_TIME, metric=model.realtime_eval_metric)
        if eval_res['res'] is None:
            continue

        total_eval_results = insert_eval_res(model_mid, model_version, eval_res)
        
        target_res = list()
        for er in total_eval_results:
            if 'metric' in er and er['metric'] == model.realtime_eval_metric:
                target_res.append(er)
        # 评估结果过少，不进行报警判断
        if len(target_res) < MIN_EVAL_RESULTS:
            continue

        long_time_loss = 0
        for es in target_res:
            long_time_loss += es['res']
        long_time_loss = long_time_loss / len(target_res)
        latest_result = target_res[0]
        reminder_data = {
            'ts': latest_result['ts'],
            'res': long_time_loss,
            'metric': model.realtime_eval_metric,
            'warning': False
        }
        
        try:
            evaluate_result = json.loads(model.evaluate_results.replace("'", '"'))
            if model.opt_use == 1 and 'opt' in evaluate_result:
                evaluate_result = evaluate_result['opt']
            elif model.opt_use == 0 and 'origin' in evaluate_result:
                evaluate_result = evaluate_result['origin']
        except:
            evaluate_result = None
        if not evaluate_result:
            logger.warning('M{}V{}\'s evalutate_results not found!'.format(model_mid, model_version))
            continue
        
        warning_gate = model.warning_gate if model.warning_gate is not None else 5.0
        origin_eval_res = evaluate_result[model.realtime_eval_metric]
        
        if long_time_loss >= warning_gate * origin_eval_res:
            reminder_data['warning'] = True

            reminder_title = '模型"{}"实时评估误差超出阈值！'.format(model.name)
            reminder_remark = '模型训练时误差({})为{}，实时评估误差({})为{}，超出设定的倍数{}'\
                              .format(model.realtime_eval_metric, origin_eval_res, 
                                      model.realtime_eval_metric, reminder_data['res'], warning_gate)
            new_reminder_args = {
                'rtype': 'model',
                'pid': None,
                'mid': model_mid,
                'version': model_version,
                'title': reminder_title,
                'remark': reminder_remark,
                'unit': model.unit
            }
            reminder_list.append(new_reminder_args)

            web_socket_data = {
                'mid': model_mid,
                'version': model_version,
                'ts': reminder_data['ts'],
                'origin_eval': origin_eval_res,
                'realtime_eval': reminder_data['res'],
                'warning_gate': warning_gate,
                'unit': model.unit
            }
            with flask_app.app_context():
                logger.info('emit websocket: M{}V{}'.format(model_mid, model_version))
                send_websocket_msg('realtime_evaluate', web_socket_data, room=str(model.unit), broadcast=False)

        model_update_args = {
            'mid': model_mid,
            'version': model_version,
            'data': {'realtime_evaluate_results': json.dumps(reminder_data)}
        }
        model_updates.append(model_update_args)
    
    with flask_app.app_context():
        Reminder.create_reminders(reminder_list)
        Model.update_models(model_updates)


def get_metric_method(name_str: str):
    metric_func = None
    try:
        if name_str != 'r2_score':
            metric_func = getattr(hd.evaluation, name_str)
    except AttributeError:
        print('[ERROR] metric "{}" not support!'.format(name_str))
    except Exception as e:
        raise e
    return metric_func


def evaluate_model(model_category, yname, ts: int, duration: int, metric: str) -> dict:
    df_dict = {'pred': [], 'target': []}
    
    start_time = ts - duration + 1
    with result_redis.redis_client.pipeline() as p:
        for i in range(duration):
            key = '{}-{}-{}'.format(yname, model_category, start_time + i)
            p.get(key)
        res_list = p.execute()
    
    for res in res_list:
        if res:
            data = json.loads(res)
            df_dict['pred'].append(data['pred']['value'])
            df_dict['target'].append(data['current'])

    eval_res = None
    if len(df_dict['pred']) == len(df_dict['target']) and len(df_dict['pred']) > 0:
        method = get_metric_method(metric)
        if method:
            eval_res = method(df_dict['target'], df_dict['pred'])

    return {
        'metric': metric,
        'res': eval_res,
        'ts': ts
    }


def insert_eval_res(model_mid, model_version, eval_res: dict):
    key = 'M{}V{}_realtime_eval'.format(model_mid, model_version)

    if result_redis.redis_client.exists(key):
        # 若已有评估结果，则将最新结果插入到列表头
        eval_results = json.loads(result_redis.read(key))
        eval_results.insert(0, eval_res)
        # 若评估结果超出，则删除末尾结果（即最古老的结果）
        ex_num = int(EXPIRE_TIME / CYCLE_TIME)
        if len(eval_results) > ex_num:
            eval_results.pop()
        result_redis.write(key, json.dumps(eval_results), expire=EXPIRE_TIME)
    else:
        eval_results = [eval_res]
        value = json.dumps(eval_results)
        result_redis.write(key, value, expire=EXPIRE_TIME)
    
    return eval_results
