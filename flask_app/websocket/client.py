import socketio
import time
import sys


class TestClient(object):
    def __init__(self, id, room) -> None:
        self.id = id
        self.room = room
        self.sio = socketio.Client()

        @self.sio.on('connect', namespace='/websocket')
        def connect():
            self.sio.emit('join', {'rooms': [self.room, ]}, namespace='/websocket')

        @self.sio.on('realtime', namespace='/websocket')
        def on_data(data):
            print(f"[id {self.id} room:{self.room} ts:{int(time.time())}] realtime data is : %s \n\n"%data)
            print("real_time received" + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))

        @self.sio.on('predict', namespace='/websocket')
        def on_data(data):
            print(f"[id {self.id} room:{self.room} ts:{int(time.time())}] predict data is : %s \n\n" % data)

        @self.sio.on('warning', namespace='/websocket')
        def on_data(data):
            print(f"[id {self.id} room:{self.room} ts:{int(time.time())}] warning data is : %s \n\n" % data)

        @self.sio.on('selection', namespace='/websocket')
        def on_data(data):
            print(f"[id {self.id} room:{self.room} ts:{int(time.time())}] warning data is : %s \n\n" % data)

        @self.sio.on('optimize', namespace='/websocket')
        def on_data(data):
            print(f"[id {self.id} room:{self.room} ts:{int(time.time())}] warning data is : %s \n\n" % data)

        @self.sio.on('train', namespace='/websocket')
        def on_data(data):
            # print(f"[id {self.id} room:{self.room} ts:{int(time.time())}] warning data is : %s \n\n"%data)
            print(data)

    def run(self):
        self.sio.connect(url='http://127.0.0.1:8010/websocket')
        self.sio.wait()


if __name__ == '__main__':
    id = 123
    room = 3
    client = TestClient(id, room)
    client.run() 
