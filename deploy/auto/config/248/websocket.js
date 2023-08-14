import Vue from 'vue'
import VueSocketIO from 'vue-socket.io'
import ClientSocketIO from 'socket.io-client'
const file = require('@/static/config.json')
const socketPath = file.websocketPath || 'http://192.168.0.123:28010/websocket'

Vue.use(new VueSocketIO({
  debug: false,
  // connection: ClientSocketIO.connect('http://106.55.173.219:39003/websocket'),
  connection: ClientSocketIO.connect('http://172.17.86.16:28010/websocket'),

  // connection: ClientSocketIO.connect('http://192.168.0.123:28010/websocket'),
  // connection: ClientSocketIO.connect('http://192.168.0.106:29003/websocket'),

  // 内网访问
  // connection: ClientSocketIO.connect('http://172.17.86.17:28010/websocket'),
  // connection: ClientSocketIO.connect('http://172.17.86.17:29003/websocket'),
  // connection: ClientSocketIO.connect(socketPath),
  // connection: ClientSocketIO.connect('http://106.55.173.219:22228/websocket'),
  cors_allowed_origins: '*',
  transports: ['websocket'],
}))
