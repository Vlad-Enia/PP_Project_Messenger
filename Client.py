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
BUFFER_SIZE = 4096000
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
        msg = pickle.loads(sender_socket.recv(BUFFER_SIZE))
        sender = msg['sender']
        if msg['type'] == 'msg':
            encrypted_message = msg['body']
            decrypted_message = rsa.decrypt(encrypted_message, private_key).decode()
            msg_list.append(decrypted_message)
            log_message(f'{dir_path}/{client_id}_received_messages.txt', sender, decrypted_message.encode('utf8'))
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

    message = pickle.loads(sock.recv(BUFFER_SIZE))
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            window.close()
            exit()
        elif event == '-BUTTON-':
            cl_id = values["-ID-"]
            send_msg('server', 'id', cl_id, cl_id, sock)
            message = pickle.loads(sock.recv(BUFFER_SIZE))
            window['-SERVER_MESSAGE-'].update(message['body'])
            window.refresh()
            if message['type'] == 'register_ok':
                formatted_public_key = public_key.save_pkcs1(format='DER')
                send_msg('server', 'pbkey', cl_id, formatted_public_key, sock)
                msg = pickle.loads(sock.recv(BUFFER_SIZE))
                if msg['type'] == 'recipient_id':
                    recipient_id = msg['body']
                    recipient_formatted_public_key = sock.recv(BUFFER_SIZE)
                    recipient_public_key = rsa.key.PublicKey.load_pkcs1(recipient_formatted_public_key, format='DER')
                    print(f'{recipient_id} connected! Public key: {recipient_public_key}\n')
                    break
    window.close()
    return sock, cl_id, recipient_id, recipient_public_key

def show_message(frame_title, msg, justification):
    window.extend_layout(
        window['-CHAT-'],
        [
            [sg.Frame
                (
                '',
                [[sg.Frame(f'{frame_title}',
                           [[sg.Text(f'{msg}', background_color=BACKGROUND_COLOR, font=FONT)]],
                           background_color=BACKGROUND_COLOR, font=FONT)]],
                expand_x=True,
                element_justification=justification,
                border_width=0,
                background_color=BACKGROUND_COLOR,
                pad=0,

            )
            ],
            [sg.Text('', size=TEXT_ELEMENT_WIDTH, background_color=BACKGROUND_COLOR, pad=0)]
        ]
    )

    window['-CHAT-'].contents_changed()

def create_emoji_dict():
    emoji_dict = {
        '-GRINNING_FACE-': 'Emojis/grinning_face.png',
        '-BEAMING_FACE-': 'Emojis/beaming_face.png',
        '-LAUGH_TEARS': 'Emojis/laugh_tears.png',
        '-WINK-': 'Emojis/wink.png',
        '-ANGRY-': 'Emojis/angry.png',
        '-HEART-': 'Emojis/heart.png'
    }
    return emoji_dict

server_socket, client_id, recipient_id, recipient_public_key = connect_and_register(SERVER_ADDRESS, SERVER_PORT)
dir_path = create_client_dir(client_id)

WINDOW_WIDTH = 700
WINDOW_HEIGHT = 1000
WINDOW_COLOR = '#6e777f'
BACKGROUND_COLOR = '#373e47'
BUTTON_COLOR = '#2d333b'
BUTTON_COLOR_HOVER = '#22272e'
TEXT_ELEMENT_WIDTH = 70
FONT = ('Calibri', 14)
EMOJI_BUTTON_IMAGE_SIZE = (35, 35)

"""
    The layout is as follows:
        -   only one column
        -   each message is within a text element
        -   text elements are inside frames, that
            -   have as title the sender
            -   have visible borders
        -   each of the visible frames are placed inside invisible frames that
            -   are as wide as the column
            -   don't have a title
            -   have invisible borders
            -   justify the visible frames to either right (sent messages), or left (received messages)
        -   below each invisible frame, there is a text element that
            -   has no text
            -   is as wide as column
            -   makes it possible for the invisible frame to stretch as wide as the column
            -   also adds some vertical space between visible frames
"""

emoji_dict = create_emoji_dict()
column_layout = []
layout = [
    [
        sg.Frame('', [[sg.Column(layout=column_layout, key='-CHAT-', scrollable=True, expand_x=True, expand_y=True,
                                 vertical_scroll_only=True, pad=20, background_color=BACKGROUND_COLOR,
                                 element_justification='right')]], size=(WINDOW_WIDTH, WINDOW_HEIGHT - 100),
                 background_color=BACKGROUND_COLOR)

    ],
    [
        sg.In(size=(25, 1), enable_events=True, key="-SEND_TEXT-"),
        sg.Button('Send', enable_events=True, key='-SEND_BUTTON-', bind_return_key=True, font=FONT, button_color=BUTTON_COLOR),
        sg.Button("\U0001F642", enable_events=True, key='-EMOJI_BUTTON-', font=FONT, button_color=BUTTON_COLOR),
        sg.Frame("Emojis",[

            [sg.pin(sg.Button(key=emoji, image_filename=emoji_dict[emoji], image_size=EMOJI_BUTTON_IMAGE_SIZE, image_subsample=3, enable_events=True, button_color=BUTTON_COLOR, visible=True)) for emoji in emoji_dict.keys()]
        ], visible=True, key='-EMOJI_FRAME-',  size=(400, 70), element_justification='c')

    ]
]
window = sg.Window(f'{client_id}\'s chat window', layout, size=(WINDOW_WIDTH, WINDOW_HEIGHT), keep_on_top=True, finalize=True)
window['-SEND_BUTTON-'].bind('<Enter>', '-BUTTON_ENTER-')
window['-SEND_BUTTON-'].bind('<Leave>', '-BUTTON_LEAVE-')
window['-EMOJI_BUTTON-'].bind('<Enter>', '-BUTTON_ENTER-')
window['-EMOJI_BUTTON-'].bind('<Leave>', '-BUTTON_LEAVE-')

received_msg_list = []
received_msg_list_copy = []

t = Thread(target=rec_msg, args=(server_socket, received_msg_list))
t.daemon = True
t.start()

emojis_visible = True

while True:
    event, values = window.read(timeout=100)

    if event == sg.TIMEOUT_KEY and len(received_msg_list) != len(received_msg_list_copy):
        show_message(recipient_id, received_msg_list[-1], 'l')
        received_msg_list_copy = copy.deepcopy(received_msg_list)
    elif event == sg.WIN_CLOSED:
        break

    elif event == '-SEND_BUTTON--BUTTON_ENTER-':
        window['-SEND_BUTTON-'].update(button_color=BUTTON_COLOR_HOVER)
    elif event == '-SEND_BUTTON--BUTTON_LEAVE-':
        window['-SEND_BUTTON-'].update(button_color=BUTTON_COLOR)
    elif event == '-EMOJI_BUTTON--BUTTON_ENTER-':
        window['-EMOJI_BUTTON-'].update(button_color=BUTTON_COLOR_HOVER)
    elif event == '-EMOJI_BUTTON--BUTTON_LEAVE-':
        window['-EMOJI_BUTTON-'].update(button_color=BUTTON_COLOR)

    elif event == '-SEND_BUTTON-':
        msg = values['-SEND_TEXT-']
        if len(msg) > 50:
            sg.popup('Message limit is 50 characters!')
        else:
            window['-SEND_TEXT-'].update('')  # clear input box when sending
            show_message(client_id, msg, 'r')

            log_message(f'{dir_path}/message_history_log.txt', client_id, msg)
            log_message(f'{dir_path}/{client_id}_sent_messages.txt', client_id, msg)

            msg_encrypted = rsa.encrypt(msg.encode('utf8'), recipient_public_key)
            send_msg(recipient_id, 'msg', client_id, msg_encrypted, server_socket)

    elif event == '-EMOJI_BUTTON-':
        if not emojis_visible:
            for emoji in emoji_dict.keys():
                window[emoji].update(visible=True)
            window['-EMOJI_FRAME-'].update(visible=True)
            emojis_visible = True

        else:
            for emoji in emoji_dict.keys():
                window[emoji].update(visible=False)
            window['-EMOJI_FRAME-'].update(visible=False)
            emojis_visible = False

        # msg = "\U0001F642"
        # window['-SEND_TEXT-'].update('')  # clear input box when sending
        # show_message(client_id, msg, 'r')
        #
        # log_message(f'{dir_path}/message_history_log.txt', client_id, msg.encode('utf8'))
        # log_message(f'{dir_path}/{client_id}_sent_messages.txt', client_id, msg.encode('utf8'))
        #
        # msg_encrypted = rsa.encrypt(msg.encode('utf8'), recipient_public_key)
        # send_msg(recipient_id, 'msg', client_id, msg_encrypted, server_socket)



server_socket.close()
window.close()
