import io
import socket
import pickle
import rsa
import PySimpleGUI as sg
import shutil
import copy
import os
from threading import Thread
from PIL import Image
from Crypto.Util.Padding import pad, unpad
from Crypto.Cipher import AES


def create_client_dir(client_id):
    dir_path = f'./{client_id}_messages'
    if os.path.isdir(dir_path):
        shutil.rmtree(dir_path)
    if client_id != '':
        os.mkdir(dir_path)
        os.mkdir(os.path.join(dir_path, 'sent_images'))
        os.mkdir(os.path.join(dir_path, 'received_images'))
    return dir_path


def log_message(filename, sender, message):
    f = open(filename, 'a')
    f.write(f'{sender}: {message}\n')
    f.close()


def log_image(filename, img_bytes):
    image = Image.open(io.BytesIO(img_bytes))
    image.save(filename)


def rec_msg(sender_socket):
    while True:
        msg = pickle.loads(sender_socket.recv(BUFFER_SIZE))
        sender = msg['sender']
        if msg['type'] == 'msg':
            encrypted_message = msg['body']
            decrypted_message = rsa.decrypt(encrypted_message, private_key).decode()
            global received_msg_number
            global received_msg_list
            received_msg_number += 1
            received_msg_list.append(decrypted_message)
            log_message(f'{dir_path}/{client_id}_received_messages.txt', sender, decrypted_message)
            log_message(f'{dir_path}/message_history_log.txt', sender, decrypted_message)
            print(f'{sender}: {decrypted_message}')
        if msg['type'] == 'img':
            global received_images_number
            global received_images_list
            received_images_number += 1
            img = decrypt_image(msg['body'])
            received_images_list.append(img)
            log_image(f'{dir_path}/received_images/image{received_images_number}.png', img)


def encrypt_image(img):
    cipher = AES.new(recipient_aes_key, AES.MODE_CBC)
    img_enc = cipher.encrypt(pad(img, AES.block_size))
    iv = cipher.iv
    return (img_enc, iv)


def decrypt_image(msg_enc):
    img_enc = msg_enc[0]
    iv = msg_enc[1]
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    img = unpad(cipher.decrypt(img_enc), AES.block_size)
    return img


def send_msg(recipient, msg_type, sender, msg, sender_socket):
    if msg_type == 'msg':
        encrypted_msg = rsa.encrypt(msg.encode('utf8'), recipient_public_key)
    elif msg_type == 'img':
        encrypted_msg = encrypt_image(msg)
    else:
        encrypted_msg = msg
    d = {
        'type': msg_type,
        'sender': sender,
        'recipient': recipient,
        'body': encrypted_msg
    }
    sender_socket.send(pickle.dumps(d))


def connect_and_register(server_address, server_port):
    sock = socket.socket()
    sock.connect((server_address, server_port))
    print('Connected to Server')

    layout = [
        [sg.Text("Python Messaging App", font=FONT)],
        [sg.Text("Hello! Please register using an unique ID.", key='-SERVER_MESSAGE-', font=FONT)],
        [
            sg.In(size=(25, 21), enable_events=True, key="-ID-", font=FONT),
            sg.Button('Register', key='-BUTTON-', bind_return_key=True, font=FONT, button_color=BUTTON_COLOR)
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

                    print(f'{cl_id}\'s AES Key: {aes_key}')
                    encrypted_aes_key = rsa.encrypt(aes_key, recipient_public_key)
                    send_msg(recipient_id, 'aes', cl_id, encrypted_aes_key, sock)

                    msg = pickle.loads(sock.recv(BUFFER_SIZE))
                    recipient_aes_key = rsa.decrypt(msg['body'], private_key)
                    print(f'{recipient_id}\'s AES Key: {recipient_aes_key}')
                    break
    window.close()
    return sock, cl_id, recipient_id, recipient_public_key, recipient_aes_key


def show_message(frame_title, msg, justification):
    """
        The layout is as follows:
            -   only one column
            -   each message is within a text element
            -   text elements are inside frames, that
                --   have as title the sender
                --   have visible borders
            -   each of the visible frames are placed inside invisible frames that
                --   are as wide as the column
                --   don't have a title
                --   have invisible borders
                --   justify the visible frames to either right (sent messages), or left (received messages)
            -   below each invisible frame, there is a text element that
                --   has no text
                --   is as wide as column
                --   makes it possible for the invisible frame to stretch as wide as the column
                --   also adds some vertical space between visible frames
    """
    window.extend_layout(
        window['-CHAT-'],
        [
            [sg.Frame('',
                      [[sg.Frame(f'{frame_title}',
                                 [[sg.Text(f'{msg}', background_color=BACKGROUND_COLOR, font=FONT)]],
                                 background_color=BACKGROUND_COLOR, font=FONT)]],
                      expand_x=True,
                      element_justification=justification,
                      border_width=0,
                      background_color=BACKGROUND_COLOR,
                      pad=0,)],

            [sg.Text('', size=TEXT_ELEMENT_WIDTH, background_color=BACKGROUND_COLOR, pad=0)]
        ]
    )
    window['-CHAT-'].contents_changed()


def show_image(frame_title, img, justification):
    """
        The layout is as follows:
            -   only one column
            -   each message is within an image element
            -   text elements are inside frames, that
                --   have as title the sender
                --   have visible borders
            -   each of the visible frames are placed inside invisible frames that
                --   are as wide as the column
                --   don't have a title
                --   have invisible borders
                --   justify the visible frames to either right (sent messages), or left (received messages)
            -   below each invisible frame, there is a text element that
                --   has no text
                --   is as wide as column
                --   makes it possible for the invisible frame to stretch as wide as the column
                --   also adds some vertical space between visible frames
    """
    window.extend_layout(
        window['-CHAT-'],
        [
            [sg.Frame('',
                      [[sg.Frame(f'{frame_title}',
                                 [[sg.Image(data=img)]],
                                 background_color=BACKGROUND_COLOR, font=FONT)]],
                      expand_x=True,
                      element_justification=justification,
                      border_width=0,
                      background_color=BACKGROUND_COLOR,
                      pad=0, )],

            [sg.Text('', size=TEXT_ELEMENT_WIDTH, background_color=BACKGROUND_COLOR, pad=0)]
        ]
    )
    window['-CHAT-'].contents_changed()


def create_emoji_dict():
    emoji_dict = {
        '-GRINNING_FACE-': 'Emojis/grinning_face.png',
        '-BEAMING_FACE-': 'Emojis/beaming_face.png',
        '-LAUGH_TEARS': 'Emojis/laugh_tears.png',
        '-SMILE-': 'Emojis/smile.png',
        '-WINK-': 'Emojis/wink.png',
        '-SUNGLASSES-': 'Emojis/sunglasses.png',
        '-ANGRY-': 'Emojis/angry.png',
        '-HEART-': 'Emojis/heart.png'
    }
    return emoji_dict


SERVER_ADDRESS = '127.0.0.1'
SERVER_PORT = 6001
BUFFER_SIZE = 4096000
BLOCK_SIZE = 16
public_key, private_key = rsa.newkeys(512)
aes_key = os.urandom(BLOCK_SIZE)
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 950
WINDOW_COLOR = '#6e777f'
BACKGROUND_COLOR = '#373e47'
BUTTON_COLOR = '#2d333b'
BUTTON_COLOR_HOVER = '#22272e'
TEXT_ELEMENT_WIDTH = 95
FONT = ('Calibri', 14)
EMOJI_BUTTON_IMAGE_SIZE = (35, 35)

server_socket, client_id, recipient_id, recipient_public_key, recipient_aes_key = connect_and_register(SERVER_ADDRESS,
                                                                                                       SERVER_PORT)
dir_path = create_client_dir(client_id)

emoji_dict = create_emoji_dict()
column_layout = []
file_types = (("PNG", "*.png"), ("JPEG", "*.jpg"))

layout = [
    [
        sg.Frame('',
                 layout=[
                     [
                         sg.Column(layout=column_layout, key='-CHAT-', scrollable=True, expand_x=True, expand_y=True,
                                   vertical_scroll_only=True, pad=20, background_color=BACKGROUND_COLOR,
                                   element_justification='right')
                     ]
                 ],
                 size=(WINDOW_WIDTH, WINDOW_HEIGHT - 100),
                 background_color=BACKGROUND_COLOR)

    ],
    [
        sg.In(enable_events=True, key='-FILE_PATH-', visible=False),

        sg.Frame(' ', border_width=0,
                 layout=[
                     [
                         sg.In(size=(20, 1), enable_events=True, key="-SEND_TEXT-", font=FONT),
                         sg.Button('Send', enable_events=True, key='-SEND_BUTTON-', bind_return_key=True, font=FONT, button_color=BUTTON_COLOR),
                         sg.FileBrowse('Image', target='-FILE_PATH-', file_types=file_types, key='-FILE_BROWSE-', font=FONT, button_color=BUTTON_COLOR, enable_events=True),
                         sg.Button("\U0001F642", enable_events=True, key='-EMOJI_BUTTON-', font=FONT, button_color=BUTTON_COLOR),
                     ]
                 ],
                 size=(400, 70),
                 element_justification='c'),

        sg.Frame("Emojis",
                 layout=[
                     [
                         sg.pin(
                             sg.Button(key=emoji, image_filename=emoji_dict[emoji], image_size=EMOJI_BUTTON_IMAGE_SIZE,
                                       image_subsample=3, enable_events=True, button_color=BUTTON_COLOR, visible=True))
                         for emoji in emoji_dict.keys()
                     ]
                 ],
                 key='-EMOJI_FRAME-',
                 size=(500, 70),
                 element_justification='c')
    ]
]


window = sg.Window(f'{client_id}\'s chat window', layout, size=(WINDOW_WIDTH, WINDOW_HEIGHT), keep_on_top=True, finalize=True)
# button_list_enter = ['-SEND_BUTTON-', '-EMOJI_BUTTON-', '-FILE_BROWSE-']
# button_list_leave = ['-SEND_BUTTON-', '-EMOJI_BUTTON-', '-FILE_BROWSE-']
# window['-SEND_BUTTON-'].bind('<Enter>', '+-BUTTON_ENTER-')
# window['-SEND_BUTTON-'].bind('<Leave>', '+-BUTTON_LEAVE-')
# window['-EMOJI_BUTTON-'].bind('<Enter>', '+-BUTTON_ENTER-')
# window['-EMOJI_BUTTON-'].bind('<Leave>', '+-BUTTON_LEAVE-')
# window['-FILE_BROWSE-'].bind('<Enter>', '+-BUTTON_ENTER-')
# window['-FILE_BROWSE-'].bind('<Leave>', '+-BUTTON_LEAVE-')
# for index in range(len(button_list_enter)):
#     # window[button_list_enter[index]].bind('<Enter>', '+-BUTTON_ENTER-')
#     button_list_enter[index] += '+-BUTTON_ENTER'
#
# for index in range(len(button_list_leave)):
#     # window[button_list_leave[index]].bind('<Leave>', '+-BUTTON_LEAVE-')
#     button_list_leave[index] += '+-BUTTON_LEAVE'
#
#
# for emoji in emoji_dict.keys():
#     window[emoji].bind('<Enter>', '+-BUTTON_ENTER-')
#     window[emoji].bind('<Leave>', '+-BUTTON_LEAVE-')
#     button_list_enter.append(emoji + '+-BUTTON_ENTER-')
#     button_list_leave.append(emoji + '+-BUTTON_LEAVE-')


received_msg_number = 0
received_msg_number_copy = 0
received_msg_list = []

received_images_number = 0
received_images_number_copy = 0
received_images_list = []
sent_images = 0

t = Thread(target=rec_msg, args=(server_socket,))
t.daemon = True
t.start()

emojis_visible = True
image_selected = False

while True:
    window['-CHAT-'].contents_changed()
    # this fixes the bug where, when there are a lot of messages and the scrollbar activates,
    # there would be a delay of one message
    event, values = window.read(timeout=100)
    if event == sg.TIMEOUT_KEY:
        if received_msg_number != received_msg_number_copy:
            msg = received_msg_list[-1]
            print(f'{recipient_id}: {msg}')
            received_msg_number_copy = copy.copy(received_msg_number)
            show_message(recipient_id, msg, 'l')

        elif received_images_number != received_images_number_copy:
            print(f'{recipient_id}: sent image')
            received_images_number_copy = copy.copy(received_images_number)
            show_image(recipient_id, received_images_list[-1], 'l')

    elif event == sg.WIN_CLOSED:
        break

    # elif event == '-SEND_BUTTON--BUTTON_ENTER-':
    #     window['-SEND_BUTTON-'].update(button_color=BUTTON_COLOR_HOVER)
    # elif event == '-SEND_BUTTON--BUTTON_LEAVE-':
    #     window['-SEND_BUTTON-'].update(button_color=BUTTON_COLOR)
    # elif event == '-EMOJI_BUTTON--BUTTON_ENTER-':
    #     window['-EMOJI_BUTTON-'].update(button_color=BUTTON_COLOR_HOVER)
    # elif event == '-EMOJI_BUTTON--BUTTON_LEAVE-':
    #     window['-EMOJI_BUTTON-'].update(button_color=BUTTON_COLOR)
    # elif event == '-FILE_BROWSE--BUTTON_ENTER-':
    #     window['-FILE_BROWSE-'].update(button_color=BUTTON_COLOR_HOVER)
    # elif event == '-FILE_BROWSE--BUTTON_LEAVE-':
    #     window['-FILE_BROWSE-'].update(button_color=BUTTON_COLOR)

    # elif event in button_list_enter or event in button_list_leave:
    #     button_event = event.split('+')
    #     print(button_event)
    #     if button_event[1] == '-BUTTON_LEAVE-':
    #         window[button_event[0]].update(button_color=BUTTON_COLOR)
    #     else:
    #         window[button_event[0]].update(button_color=BUTTON_COLOR_HOVER)

    elif event == '-FILE_PATH-':
        window['-FILE_BROWSE-'].update(button_color=BUTTON_COLOR)
        image_selected = True

    elif event == '-SEND_BUTTON-':
        if not image_selected:
            msg = values['-SEND_TEXT-']
            if msg != '':
                window['-SEND_TEXT-'].update('')  # clear input box when sending
                if len(msg) > 50:
                    sg.popup('Message limit is 50 characters!')
                else:
                    show_message(client_id, msg, 'r')
                    log_message(f'{dir_path}/message_history_log.txt', client_id, msg)
                    log_message(f'{dir_path}/{client_id}_sent_messages.txt', client_id, msg)
                    send_msg(recipient_id, 'msg', client_id, msg, server_socket)

        else:
            sent_images += 1
            image_selected = False
            if values['-FILE_PATH-'] != '':
                path = values['-FILE_PATH-']
                window['-FILE_PATH-'].update('')
                if os.path.exists(path):
                    image = Image.open(path)
                    image.thumbnail((500, 500))
                    image_bytes = io.BytesIO()
                    image.save(image_bytes, format='PNG')
                    send_msg(recipient_id, 'img', client_id, image_bytes.getvalue(),
                             server_socket)
                    show_image(client_id, image_bytes.getvalue(), 'r')

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

    elif event in emoji_dict.keys():
        sent_images += 1
        path = emoji_dict[event]
        if os.path.exists(path):
            image = Image.open(path)
            image_bytes = io.BytesIO()
            image.save(image_bytes, format='PNG')
            send_msg(recipient_id, 'img', client_id, image_bytes.getvalue(),
                     server_socket)
            show_image(client_id, image_bytes.getvalue(), 'r')
            log_image(f'{dir_path}/sent_images/image{sent_images}.png', image_bytes.getvalue())

server_socket.close()
window.close()
