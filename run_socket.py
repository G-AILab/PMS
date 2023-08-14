
import json
import time
import traceback
from threading import Lock
from typing import Optional, Union
from redis import Redis
import random
import flask
from flask import Flask
from flask_socketio import SocketIO, join_room, leave_room, rooms
from redis.client import PubSub
from socketio import BaseManager
from loguru import logger

from flask_app.websocket.redis_pub_sub import  redis_obj,  CHANNEL


flask_app = Flask("power_model_station_socketio")
sio = SocketIO(flask_app, cors_allowed_origins='*',ping_interval=60,ping_timeout=10)
NAMESPACE = '/websocket'
socketio_background_task_existed = False
socketio_background_task_lock = Lock()
num = 0




def handle_realtime(socket_io, realtime_data):
    is_empty, existed_room = check_rooms_is_empty(socket_io)
    if is_empty:
        return 
    # 发送单个 realtime 数据
    for point, value in realtime_data.items():
        socket_io.emit('realtime', {point:value, 'ts': realtime_data['latest']}, namespace=NAMESPACE, to=f"realtime_{point}") # item_data['data']
            # socket_io.emit('realtime', {point:value}, namespace=NAMESPACE, to=point) # item_data['data']
        
    # 发送所有的 realtime 数据
    if 'all' in existed_room:
        socket_io.emit('realtime', realtime_data, namespace=NAMESPACE, to='all') # item_data['data']



def handle_point_check(socket_io, point_check_data, event):
    """_summary_

    Args:
        socket_io (_type_): _description_
        predict_data (_type_): _description_
        
    """
    is_empty, existed_room = check_rooms_is_empty(socket_io)
    if is_empty:
        return 
    # 发送单个 realtime 数据
    socket_io.emit(event, point_check_data, namespace=NAMESPACE, to=f"{event}_{point_check_data['data']['point_name']}") # item_data['data']
            # socket_io.emit('realtime', {point:value}, namespace=NAMESPACE, to=point) # item_data['data']



def handle_download_process(socket_io, download_process_data, event):
    is_empty, existed_room = check_rooms_is_empty(socket_io)
    print("existed_room", existed_room)
    if is_empty:
        logger.info("room is empty, return.")
        return 
    # print(f"type of data: {type(download_process_data)}")
    sid = download_process_data.get('data', {}).pop('sid', '')
    # print(f"emit message to {event} with sid {sid}: {download_process_data}")
    socket_io.emit(event, download_process_data, namespace=NAMESPACE, to=sid, broadcast=False) # item_data['data']




def deal_item(item):
    # type为subscribe 跳过
    if item['type'] == 'subscribe':
        return None, None, None
    event = item['channel']
    if isinstance(event, bytes):
        event = event.decode('utf-8')
    item_data = json.loads(item['data']) or {}
    room : Optional[str]= str(item_data.get('unit', None)) #  "unit_{}".format(item_data.get('unit', ''))
    item_data['time_str'] = time.strftime('%F %T')
    # print(f"event:{event}, data:{item_data}, room:{room}")
    return event, item_data, room



def check_rooms_is_empty(socket_io: SocketIO):
    manager: BaseManager = socket_io.server.manager
    namespaces = manager.get_namespaces()
    # namespace 不存在
    if not (NAMESPACE in namespaces):
        return True, None
    # 选择指定namespace中存在的room列表（机组）
    now_rooms = list(manager.rooms[NAMESPACE].keys())
    # print("now rooms map is:", manager.rooms[NAMESPACE])
    # 获取当前存在的活跃room , 除了 client 本身和 None
    existed_other_room =  set(now_rooms) - set([None]) # list(filter(is_format_unit_room, now_rooms))
    # print(f"exist room is :{existed_other_room}")
    if len(existed_other_room) == 0:
        return True, None
    else:
        return False, existed_other_room


def background_task_end():
    print(f"[INFO] end task.")
    global socketio_background_task_existed, num
    with socketio_background_task_lock:
        num = 0
        socketio_background_task_existed = False


def notice(redis_obj: Redis, socket_io: SocketIO):
    try:
        while True:
            # 和有没有room无关不应该去判断是否存在room 才去 notice
            sub = redis_obj.pubsub()
            is_exception = False
            try:
                sub.subscribe(*CHANNEL.values())
                emit_redis_data(sub=sub, socket_io=socket_io)
            except Exception as e:
                is_exception = True
                print(f"[{time.strftime('%F %T')} ERROR]  notice Exception :{e}")
            finally:
                logger.error("socket closed")
                sub.close()

            if is_exception:
                socket_io.sleep(random.randint(1, 4))
    except Exception as e:
        print(f"[{time.strftime('%F %T')} ERROR]  notice Exception :{e}")
        traceback.print_exc()
    finally:
        background_task_end()


def emit_redis_data(sub: PubSub, socket_io: SocketIO):
    # listen 到 一条数据并且发送
    for item in sub.listen():
        event, data, room = deal_item(item)
        if not (event and data and room):
            continue
        
        # 特殊处理 realtime数据
        if event == 'realtime':
            handle_realtime(socket_io, data['data'])
        elif 'point_check_' in event:
            handle_point_check(socket_io, data, event=event)
        elif  event == 'download_process':
            handle_download_process(socket_io, data, event=event)
        # elif event == 'predict':
        #     handle_predict(socket_io, data['data'])
        else:
            # 向前兼容，其他暂时保持不变
            is_empty, existed_room = check_rooms_is_empty(socket_io)  
            if is_empty:
                break
            if room in existed_room:
                manager = socket_io.server.manager
                print(f"[INFO] emit message:event:{event}, room:{room} {existed_room}")
                socket_io.emit(event, data, namespace=NAMESPACE, to=room)
            else:
                print(f"{room} not int room {existed_room}")

@sio.on('connect', namespace=NAMESPACE)
def on_connect():
    print("=" * 30)
    print("client connected")
    print("=" * 30)
    
    start_notice()


# 断开连接时自动退出所有room
@sio.on('disconnect', namespace=NAMESPACE)
def disconnect():
    sid = flask.request.sid
    for room in rooms(sid, namespace=NAMESPACE):
        leave_room(room)
    print("*" * 15, "disconnect", "*" * 15)


# 断开连接时自动退出所有room
@sio.on('leave_all', namespace=NAMESPACE)
def leave_all(data):
    logger.info(f'data:{data}')
    sid = flask.request.sid
    for room in rooms(sid, namespace=NAMESPACE):
        logger.info(f'leave:{room}.{sid}')
        leave_room(room)



def start_notice():
    global socketio_background_task_existed, num
    print(f"socketio_background_task_existed :{socketio_background_task_existed},num:{num}")
    with socketio_background_task_lock:
        if not socketio_background_task_existed:
            num = 1
            print("start backend task")
            sio.start_background_task(target=notice, redis_obj=redis_obj.redis_client, socket_io=sio)
            socketio_background_task_existed = True

# 订阅时加入room
@sio.on('join', namespace=NAMESPACE)
def on_join_room(data):
    print("\njoin request\n")
    rooms = data.get('rooms', list())
    for room in rooms:
        print(f"[{time.strftime('%F %X')} on_join_in] {flask.request.sid} join in unit room: {str(room)}")
        join_room(str(room))
    ts = int(time.time())
    t = time.strftime("%F %T")
    sio.emit('join_room_result', {"result": "join in room!!", "ts": ts, "time": t}, namespace=NAMESPACE)

def join_unit(sid, unit, event):
    """
        join unit 加入 某一机组的指定事件
    """
    if event is None:
        logger.error("加入机组指定事件失败: event为None")
        return
    join_room(f"{event}_{unit}")     
    t = time.strftime("%F %T")
    sio.emit('join_unit_event', {"result": f"{event} join in {unit}!!", "unit": unit, "time": t},to=sid, namespace=NAMESPACE)

def leave_unit(sid, unit, event):
    """
        join unit 离开 某一机组的指定事件
    """
    if event is None:
        logger.error("离开机组指定事件失败: event为None")
        return
    leave_room(f"{event}_{unit}")     
    t = time.strftime("%F %T")
    sio.emit('leave_unit_event', {"result": f"{event} event in {unit}!!", "unit": unit, "time": t},to=sid, namespace=NAMESPACE)

    
def join_points(sid, points, event):
    for point in points:
        join_room(f"{event}_{point}")     
        logger.info(f"{sid} joined : point_check_actual_{point}")   
    t = time.strftime("%F %T")
    sio.emit('join_room_result', {"result": f"{event} join in room!!", "points": points, "time": t},to=sid, namespace=NAMESPACE)


def leave_points(sid, points, event):
    for point in points:
        leave_room(f"{event}_{point}")     
        logger.info(f"{event}_{point}")   
    t = time.strftime("%F %T")
    sio.emit('leave_room_result', {"result": f"{event} laves in room!!", "leaves": points, "time": t},to=sid, namespace=NAMESPACE)


@sio.on('realtime', namespace=NAMESPACE)
def points(data):
    join_points(flask.request.sid, data.get('points', list()), 'realtime')
    leave_points(flask.request.sid, data.get('leaves', list()), 'realtime')


@sio.on('point_check_actual', namespace=NAMESPACE)
def point_check_actual_points(data):
    join_points(flask.request.sid, data.get('points', list()), 'point_check_actual')
    leave_points(flask.request.sid, data.get('leaves', list()), 'point_check_actual')

@sio.on('point_check_switch', namespace=NAMESPACE)
def point_check_switch_points(data):
    join_points(flask.request.sid, data.get('points', list()), 'point_check_switch')
    leave_points(flask.request.sid, data.get('leaves', list()), 'point_check_switch')

@sio.on('point_check_expect', namespace=NAMESPACE)
def point_check_expect_points(data):
    join_points(flask.request.sid, data.get('points', list()), 'point_check_expect')
    leave_points(flask.request.sid, data.get('leaves', list()), 'point_check_expect')

@sio.on('point_check_upper', namespace=NAMESPACE)
def point_check_upper_points(data):
    join_points(flask.request.sid, data.get('points', list()), 'point_check_upper')
    leave_points(flask.request.sid, data.get('leaves', list()), 'point_check_upper')

@sio.on('point_check_lower', namespace=NAMESPACE)
def point_check_lower_points(data):
    join_points(flask.request.sid, data.get('points', list()), 'point_check_lower')
    leave_points(flask.request.sid, data.get('leaves', list()), 'point_check_lower')
    

@sio.on('point_check_offset', namespace=NAMESPACE)
def point_check_offset_points(data):
    join_points(flask.request.sid, data.get('points', list()), 'point_check_offset')
    leave_points(flask.request.sid, data.get('leaves', list()), 'point_check_offset')
    
@sio.on('point_check_variance', namespace=NAMESPACE)
def point_check_variance_points(data):
    join_points(flask.request.sid, data.get('points', list()), 'point_check_variance')
    leave_points(flask.request.sid, data.get('leaves', list()), 'point_check_variance')

@sio.on('download_process', namespace=NAMESPACE)
def download_process(data):
    # join_unit(flask.request.sid,data.get('join', None), 'download_process')
    # leave_unit(flask.request.sid,data.get('leave', None), 'download_process')
    ...
    
@sio.on('download_sid', namespace=NAMESPACE)
def get_sid(data):
    sid = flask.request.sid
    t = time.strftime("%F %T")
    sio.emit('download_sid', {"result": "Has joined private room.", "sid": sid, "time": t}, to=sid, namespace=NAMESPACE)

# leave时，离开指定room
@sio.on('leave', namespace=NAMESPACE)
def on_leave_room(data):
    rooms = data.get('rooms', list())
    for room in rooms:
        leave_room(str(room))


if __name__ == '__main__':
    sio.run(app=flask_app, host='0.0.0.0', port=18010)
