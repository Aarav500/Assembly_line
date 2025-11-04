import time
import socketio

# Simple Python client to test the server

sio = socketio.Client()

USER_ID = "py-user-1"

@sio.event
def connect():
    print("Connected to server")

@sio.on('connected')
def on_connected(data):
    print('connected event:', data)

@sio.event
def disconnect():
    print("Disconnected from server")

@sio.on('notification')
def on_notification(data):
    print('notification:', data)

@sio.on('presence:user_online')
def on_user_online(data):
    print('user online:', data)

@sio.on('presence:user_offline')
def on_user_offline(data):
    print('user offline:', data)

if __name__ == '__main__':
    sio.connect('http://localhost:5000', transports=['websocket'], auth={'user_id': USER_ID})
    sio.emit('join_room', {'room': 'general'})
    time.sleep(0.5)
    sio.emit('notify_room', {'room': 'general', 'payload': {'hello': 'from python'}})
    time.sleep(2)
    sio.disconnect()

