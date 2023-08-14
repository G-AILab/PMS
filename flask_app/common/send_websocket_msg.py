from re import I
import traceback
import requests
from flask_app import websocket_pub

def send_websocket_msg(type, data, room=None, broadcast=True, namespace='/websocket'):
    # 将websocket的请求由 /model/emit 统一发送
    # msg = {
    #     'type': type,
    #     'data': data,
    #     'broadcast': broadcast,
    #     'namespace': namespace,
    #     'room': room
    # }
    try:
        websocket_pub.publish_data(channel=type, unit=room, data=data)
    except:
        traceback.print_exc()
        pass

