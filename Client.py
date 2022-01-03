import socket
import pickle
import rsa
from threading import Thread
import PySimpleGUI as sg
import os
import shutil
import copy

SERVER_ADDRESS = '127.0.0.1'
SERVER_PORT = 6001
public_key, private_key = rsa.newkeys(512)
print(f'Your public key: {public_key}\n')

def create_client_dir(client_id):
    dir_path = f'./{client_id}_messages'
    if os.path.isdir(dir_path):
        shutil.rmtree(dir_path)
    if client_id != '':
        os.mkdir(dir_path)
    return dir_path


def log_message(filename, sender, message):
    f = open(filename, 'a')
    f.write(f'{sender}: {message}\n')
    f.close()


def rec_msg(sender_socket, msg_list):
    while True:
        msg = pickle.loads(sender_socket.recv(4096))
        sender = msg['sender']
        encrypted_message = msg['body']
        decrypted_message = rsa.decrypt(encrypted_message, private_key).decode('utf8')
        msg_list.append(decrypted_message)
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
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            window.close()
            exit()
        elif event == '-BUTTON-':
            cl_id = values["-ID-"]
            send_msg('server', 'id', cl_id, cl_id, sock)
            message = pickle.loads(sock.recv(4096))
            window['-SERVER_MESSAGE-'].update(message['body'])
            window.refresh()
            if message['type'] == 'register_ok':
                formatted_public_key = public_key.save_pkcs1(format='DER')
                send_msg('server', 'pbkey', cl_id, formatted_public_key, sock)
                msg = pickle.loads(sock.recv(4096))
                if msg['type'] == 'recipient_id':
                    recipient_id = msg['body']
                    recipient_formatted_public_key = sock.recv(4096)
                    recipient_public_key = rsa.key.PublicKey.load_pkcs1(recipient_formatted_public_key, format='DER')
                    print(f'{recipient_id} connected! Public key: {recipient_public_key}\n')
                    break
    window.close()
    return sock, cl_id, recipient_id, recipient_public_key


server_socket, client_id, recipient_id, recipient_public_key = connect_and_register(SERVER_ADDRESS, SERVER_PORT)
dir_path = create_client_dir(client_id)

# print("Waiting for the other client to connect...")
# msg = pickle.loads(server_socket.recv(4096))
# if msg['type'] == 'recipient_id':
#     recipient_id = msg['body']
#     formatted_public_key = server_socket.recv(4096)
#     recipient_public_key = rsa.key.PublicKey.load_pkcs1(formatted_public_key, format='DER')
#     print(f'{recipient_id} connected! Public key: {recipient_public_key}\n')

WINDOW_WIDTH = 100
WINDOW_HEIGHT = 100

recipient_column = []
sender_column = []
layout = [
    [
        sg.Column(layout=recipient_column, key='-RECIPIENT-', size=(210,210), scrollable=True, vertical_scroll_only=True, expand_y=True),
        sg.Column(layout=sender_column, key='-SENDER-',size=(210,210), scrollable=True, vertical_scroll_only=True, expand_y=True)
    ],
    [
        sg.In(size=(25, 1), enable_events=True, key="-SEND_TEXT-"),
        sg.Button('Send', enable_events=True, key='-SEND_BUTTON-', bind_return_key=True)
    ]
]
window = sg.Window(f'{client_id} chat window', layout)

received_msg_list = []
received_msg_list_copy = []

t = Thread(target=rec_msg, args=(server_socket, received_msg_list))
t.daemon = True
t.start()

while True:
    event, values = window.read(timeout=100)

    if event == sg.TIMEOUT_KEY and len(received_msg_list) != len(received_msg_list_copy):

        window.extend_layout(window['-RECIPIENT-'], [[sg.Text(received_msg_list[-1], background_color='red')]])
        window['-RECIPIENT-'].contents_changed()
        window.extend_layout(window['-SENDER-'], [[sg.Text('')]])
        window['-SENDER-'].contents_changed()

        received_msg_list_copy = copy.deepcopy(received_msg_list)
    elif event == sg.WIN_CLOSED:
        break
    elif event == '-SEND_BUTTON-':
        msg = values['-SEND_TEXT-']
        window['-SEND_TEXT-'].update('')     #clear input box when sending

        window.extend_layout(window['-SENDER-'], [[sg.Text(msg,  background_color='green', justification='r')]])
        window['-SENDER-'].contents_changed()
        window.extend_layout(window['-RECIPIENT-'], [[sg.Text('')]])
        window['-RECIPIENT-'].contents_changed()

        log_message(f'{dir_path}/message_history_log.txt', client_id, msg)
        log_message(f'{dir_path}/{client_id}_sent_messages.txt', client_id, msg)

        msg_encrypted = rsa.encrypt(msg.encode('utf8'), recipient_public_key)
        send_msg(recipient_id, 'msg', client_id, msg_encrypted, server_socket)

server_socket.close()
window.close()
