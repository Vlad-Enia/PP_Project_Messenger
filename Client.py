import socket
import json
from threading import Thread

SERVER_ADDRESS = '127.0.0.1'
SERVER_PORT = 6000


def rec_msg(sender_socket):
    while True:
        message = json.loads(sender_socket.recv(4096).decode('utf_8'))


client_id = ''


def send_msg(recipient, msg_type, msg, sender_socket):
    d = {
        'type': msg_type,
        'sender': client_id,
        'recipient': recipient,
        'body': msg
    }
    sender_socket.send(json.dumps(d).encode())


def connect_and_register(server_address, server_port):
    sock = socket.socket()
    sock.connect((server_address, server_port))
    print('Connected to Server')
    cl_id = ''
    message = json.loads(sock.recv(4096))
    while message['type'] == 'register':
        print('Server:', message['body'])
        cl_id = input('ID: ')
        send_msg('server', 'id', cl_id, sock)
        message = json.loads(sock.recv(4096))
    print('Server:', message['body'])
    return sock, cl_id


server_socket, client_id = connect_and_register(SERVER_ADDRESS, SERVER_PORT)

t = Thread(target=rec_msg, args=(server_socket,))
t.daemon = True
t.start()

while True:
    msg = input('Message: ')
    send_msg('', 'msg', msg, server_socket)
