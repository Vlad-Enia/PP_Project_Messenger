import socket
import pickle
import rsa
from threading import Thread
import PySimpleGUI as sg
import os

SERVER_ADDRESS = '127.0.0.1'
SERVER_PORT = 6001
public_key, private_key = rsa.newkeys(512)
print(f'Your public key: {public_key}\n')

def rec_msg(sender_socket):
    while True:
        msg = pickle.loads(sender_socket.recv(4096))
        sender = msg['sender']
        encrypted_message = msg['body']
        decrypted_message = rsa.decrypt(encrypted_message, private_key).decode('utf8')
        log_message(f'{dir_path}/{client_id}_received_messages.txt', sender, decrypted_message)
        print(f'{sender}: {decrypted_message}')


def send_msg(recipient, msg_type, sender, msg, sender_socket):
    d = {
        'type': msg_type,
        'sender': sender,
        'recipient': recipient,
        'body': msg
    }
    sender_socket.send(pickle.dumps(d))


def connect_and_register(server_address, server_port):
    sock = socket.socket()
    sock.connect((server_address, server_port))
    print('Connected to Server')
    cl_id = ''

    layout = [
        [
            sg.Text("Python Messaging App")
        ],
        [
            sg.Text("Hello! Please register using an unique ID.", key='-SERVER_MESSAGE-')
        ],
        [
            sg.In(size=(25, 1), enable_events=True, key="-ID-"),
            sg.Button('Register', key='-BUTTON-', bind_return_key=True)
        ]
    ]
    window = sg.Window("Register Window", layout, element_justification='center', element_padding=10)

    message = pickle.loads(sock.recv(4096))
    while message['type'] == 'register':
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            break
        elif event == '-BUTTON-' or event == 'Submit':
            cl_id = values["-ID-"]
            send_msg('server', 'id', cl_id, cl_id, sock)
            message = pickle.loads(sock.recv(4096))
            window['-SERVER_MESSAGE-'].update(message['body'])
    window.close()
    print('Server:', message['body'])

    formatted_public_key = public_key.save_pkcs1(format='DER')
    send_msg('server', 'pbkey', cl_id, formatted_public_key, sock)
    return sock, cl_id


def log_message(filename, sender, message):
    f = open(filename, 'a')
    f.write(f'{sender}: {message}\n')
    f.close()


server_socket, client_id = connect_and_register(SERVER_ADDRESS, SERVER_PORT)

dir_path = f'./{client_id}_messages'

os.mkdir(dir_path)

print("Waiting for the other client to connect...")
msg = pickle.loads(server_socket.recv(4096))
if msg['type'] == 'recipient_id':
    recipient_id = msg['body']
    formatted_public_key = server_socket.recv(4096)
    recipient_public_key = rsa.key.PublicKey.load_pkcs1(formatted_public_key, format='DER')
    print(f'{recipient_id} connected! Public key: {recipient_public_key}\n')


t = Thread(target=rec_msg, args=(server_socket,))
t.daemon = True
t.start()

while True:
    msg = input()
    log_message(f'{dir_path}/message_history_log.txt',client_id, msg)
    log_message(f'{dir_path}/{client_id}_sent_messages.txt', client_id, msg)
    msg_encrypted = rsa.encrypt(msg.encode('utf8'), recipient_public_key)
    send_msg(recipient_id, 'msg', client_id, msg_encrypted, server_socket)
