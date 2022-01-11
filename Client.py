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
from datetime import datetime


def create_client_dir(client_id):
    """
    Given a client id, creates a directory dedicated to that client, that will be used to store messages and images sent/received by him.
    :param client_id: string containing a unique id of a client
    :return: path to the client's directory
    """
    dir_path = f'./{client_id}_messages'
    if os.path.isdir(dir_path):
        shutil.rmtree(dir_path)
    if client_id != '':
        os.mkdir(dir_path)
        os.mkdir(os.path.join(dir_path, 'sent_images'))
        os.mkdir(os.path.join(dir_path, 'received_images'))
    return dir_path


def log_message(filename, sender, message):
    """
    Appends to a specified path of an .txt file the line "sender: message".
    :param filename: string containing the path to a .txt file
    :param sender: string containing the id of the sender
    :param message: string containing the message that is to be stored
    """
    now = datetime.now().strftime("%d.%b.%Y. %H:%M:%S")
    f = open(filename, 'a')
    f.write(f'{sender} - {now}: {message}\n')
    f.close()


def log_image(filename, img_bytes):
    """
    Saves an image represented as a byte string to a specified path.
    :param filename: path of a location at which the image will be saved
    :param img_bytes: the image that is to be saved, represented as a byte string
    """
    image = Image.open(io.BytesIO(img_bytes))
    image.save(filename)



def rec_msg(sender_socket):
    """
    Method that intercepts all the messages received at a specified socket.
    Since this method will run in a separate thread, it will store the messages (text or image)
     in a shared list that the main thread can interact with.
    It also stores the messages on disk by calling methods log_message and log_image from above
    :param sender_socket: socket from where messages are received
    """
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
            image_path = f'{dir_path}/received_images/image{received_images_number}.png'
            log_image(image_path, img)
            log_message(f'{dir_path}/message_history_log.txt', sender, os.path.abspath(image_path))
        if msg['type'] == 'error':
            print("ERROR: " + msg['body'])
            global received_errors_number
            global received_errors_list
            received_errors_list.append(msg['body'])
            received_errors_number += 1



def encrypt_image(img):
    """
    Encrypts an image using AES in CBC mode, before sending it to a recipient.
    Uses a key that was shared by the recipient beforehand.
    :param img: image represented as a byte string
    :return: a tuple containing the encrypted image and its correspongind initialization vector, used in the encryption
    process and needed for decryption
    """
    cipher = AES.new(recipient_aes_key, AES.MODE_CBC)
    img_enc = cipher.encrypt(pad(img, AES.block_size))
    iv = cipher.iv
    return (img_enc, iv)


def decrypt_image(msg_enc):
    """
    Decrypts an image that was previously encrypted using AES using CBC mode.
    :param msg_enc: a tuple containing the encrypted image (byte string), and the initialization vector used in the
    encryption method and needed for decryption
    :return: decrypted image, represented as bytes string
    """
    img_enc = msg_enc[0]
    iv = msg_enc[1]
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    img = unpad(cipher.decrypt(img_enc), AES.block_size)
    return img


def send_msg(recipient, msg_type, sender, msg, sender_socket):
    """
    Sends a dictionary through a specified socket, containing the following information: sender, recipient, message type, message
    Before sending it, if the message type requires it, the message is encrypted.
    :param recipient: id of the client that should receive the message, or the server
    :param msg_type: message type, so that the recipient knows how to process it
    :param sender: id of the sender
    :param msg: the message that should be received by the recipient; anything that can be serialized
    :param sender_socket: socket used to send the messages
    :return:
    """
    if msg_type == 'msg':
        encrypted_msg = rsa.encrypt(msg.encode('utf8'), recipient_public_key) # text messages are encrypted using the recipient's public RSA key, that was shared with the sender beforehand
    elif msg_type == 'img':
        encrypted_msg = encrypt_image(msg)  # images are encrypted using the recipient's AES key, that was shared with the sender beforehand
    else:
        encrypted_msg = msg
    d = {
        'type': msg_type,
        'sender': sender,
        'recipient': recipient,
        'body': encrypted_msg
    }
    sender_socket.send(pickle.dumps(d)) # the dictionary is serialized and sent through the socket


def connect_and_register(server_address, server_port):
    """
    Method that is first called by the client in order to connect to a specified server.
    A GUI window will launch, so that the used can register to the server using an unique id.
    If registration was successful, the program will stall until the other client connects and successfully connects and registers.
    After that, clients will automatically exchange the following information:
    - their IDs
    - their public RSA keys, that will be used for encrypting text messages;
    obviously, a client will use the other client's public RSA key to encrypt the message, so that only the other client can decrypt it using his private key
    - their AES keys, that will be used for encrypting images; a client will encrypt an image with the other client's AES key;
    the key is encrypted using the other client's RSA public key before sending it, so that only the other client can use it to decrypt received images
    :param server_address: server ip
    :param server_port: server port
    :return: a tuple containing the follwing information
    - socket used for communication with the other client, as long as with the server
    - client ID chosen by the user when registering
    - recipient ID
    - recipient's public RSA key
    - recipient's AES key
    """

    sock = socket.socket()
    sock.connect((server_address, server_port))
    print('Connected to Server')

    layout = [                                                                                                      # layout of the GUI window
        [sg.Text("Python Messaging App", font=FONT)],
        [sg.Text("Hello! Please register using an unique ID.", key='-SERVER_MESSAGE-', font=FONT)],                 # text field for displaying messages from the server
        [
            sg.In(size=(25, 21), enable_events=True, key="-ID-", font=FONT),                                        # input field where the user writes his desired ID
            sg.Button('Register', key='-BUTTON-', bind_return_key=True, font=FONT, button_color=BUTTON_COLOR)       # button that will send the ID to the server for checking; note that the 'enter' key is bound to it
        ]
    ]
    window = sg.Window("Register Window", layout, element_justification='center', element_padding=10)

    message = pickle.loads(sock.recv(BUFFER_SIZE))                                                                  # this message is sent by the server as a confirmation that a connection request was received from the client
    while True:
        event, values = window.read()                                                                               # method window.read() returns the event that last took place in the GUI, and the values contained by the elements from the layout above

        if event == sg.WIN_CLOSED:                                                                                  # if the user closes the window, the program will end its execution
            window.close()
            exit()

        elif event == '-BUTTON-':                                                                                   # event triggered when the user pressed the button on the gui or the 'enter' button
            cl_id = values["-ID-"]                                                                                  # the client id is extracted from the input field
            send_msg('server', 'id', cl_id, cl_id, sock)                                                            # it is sent to the server; note that the message type is 'id', therefore it will not be encrypted

            message = pickle.loads(sock.recv(BUFFER_SIZE))                                                          # a message is received from the server regarding the previously sent id
            window['-SERVER_MESSAGE-'].update(message['body'])                                                      # and it is displayed on the window; the message can be a welcome from the server, meaning that the client succesfuly registered, or
                                                                                                                    # it can be a warning, if the ID is taken by the other user, or if an empty ID was sent
            window.refresh()

            if message['type'] == 'register_ok':                                                                    # if message type is 'register_ok', meaning a succesful registration
                formatted_public_key = public_key.save_pkcs1(format='DER')
                send_msg('server', 'pbkey', cl_id, formatted_public_key, sock)                                      # the client's public key is sent to the server, that will be stored in a dictionary containing the keys from both of the clients

                msg = pickle.loads(sock.recv(BUFFER_SIZE))                                                          # this is where the program stalls until the server sends the ID of the other client.

                if msg['type'] == 'recipient_id':                                                                   # when the other clients connects and registers, the server will send his id, and a communication session can begin;
                                                                                                                    # but before that, some information needs to be exchanged first
                    recipient_id = msg['body']
                    recipient_formatted_public_key = sock.recv(BUFFER_SIZE)                                         # the server, after sending the other client's ID, will immediately sent his public RSA key
                    recipient_public_key = rsa.key.PublicKey.load_pkcs1(recipient_formatted_public_key, format='DER')
                    print(f'{recipient_id} connected! Public key: {recipient_public_key}\n')

                    print(f'{cl_id}\'s AES Key: {aes_key}')
                    encrypted_aes_key = rsa.encrypt(aes_key, recipient_public_key)                                  # the client's AES key is encrypted using the other client's RSA public key received earlier, before it is sent to him (the other client)
                    send_msg(recipient_id, 'aes', cl_id, encrypted_aes_key, sock)                                   # the encrypted AES key is sent to the other client; note that the reciepient is the other client's ID received earlier,
                                                                                                                    # therefore, the server will only forward the message to him
                    msg = pickle.loads(sock.recv(BUFFER_SIZE))                                                      # the other client also sends his AES key, encrypted obviously
                    recipient_aes_key = rsa.decrypt(msg['body'], private_key)                                       # the aes key is decrypted and ready to use
                    print(f'{recipient_id}\'s AES Key: {recipient_aes_key}')
                    break                                                                                           # after all of these steps took place successfully, the window will close
    window.close()
    return sock, cl_id, recipient_id, recipient_public_key, recipient_aes_key


def show_message(frame_title, msg, justification):
    """
    Method used for displaying the text messages sent/received by the client.
    The layout is as follows:
    -   only one column
    -   each message is within a text element
    -   text elements are inside frames, that
        ----   have as title the sender
        ----   have visible borders
    -   each of the visible frames are placed inside invisible frames that
        ----   are as wide as the column
        ----   don't have a title
        ----   have invisible borders
        ----   justify the visible frames to either right (sent messages), or left (received messages)
    -   below each invisible frame, there is a text element that
        ----   has no text
        ----   is as wide as column
        ----   makes it possible for the invisible frame to stretch as wide as the column
        ----   also adds some vertical space between visible frames
    :param frame_title: the title of the frame surrounding the message, in this case will be the sender's ID
    :param msg: the text message that is going to be displayed
    :param justification: the message will be justified to either right (sent messages), or left (received messages)
    """
    window.extend_layout(
        window['-CHAT-'],
        [
            [sg.Frame('',
                      [[sg.Frame(f'{frame_title}', [[sg.Text(f'{msg}', background_color=BACKGROUND_COLOR, font=FONT)]], background_color=BACKGROUND_COLOR, font=FONT)]],
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
    Method used for displaying the image messages sent/received by the client.
    The layout is as follows:
    -   only one column
    -   each message is within an image element
    -   text elements are inside frames, that
        ----   have as title the sender
        ----   have visible borders
    -   each of the visible frames are placed inside invisible frames that
        ----   are as wide as the column
        ----   don't have a title
        ----   have invisible borders
        ----   justify the visible frames to either right (sent messages), or left (received messages)
    -   below each invisible frame, there is a text element that
        ----   has no text
        ----   is as wide as column
        ----   makes it possible for the invisible frame to stretch as wide as the column
        ----   also adds some vertical space between visible frames
    :param frame_title: the title of the frame surrounding the message, in this case will be the sender's ID
    :param img: the image that is going to be displayed
    :param justification: the message will be justified to either right (sent messages), or left (received messages)
    """
    window.extend_layout(
        window['-CHAT-'],
        [
            [sg.Frame('',
                      [[sg.Frame(f'{frame_title}', [[sg.Image(data=img)]], background_color=BACKGROUND_COLOR, font=FONT)]],
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
    """
    A method used for creating a dictionary containing the supported emojis.
    :return: a dictionary with the keys the same as the keys of the buttons for the emojis,
    and the values are the images of the emojis that are sent when a user sends an emoji.
    """
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
BUFFER_SIZE = 4096000           # buffer size used when reading from the socket
BLOCK_SIZE = 16                 # block size for AES encryption
public_key, private_key = rsa.newkeys(512)  # the client's public and private RSA keys
aes_key = os.urandom(BLOCK_SIZE)       # client's AES key
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 950
WINDOW_COLOR = '#6e777f'
BACKGROUND_COLOR = '#373e47'
BUTTON_COLOR = '#2d333b'
TEXT_ELEMENT_WIDTH = 95
FONT = ('Calibri', 14)
EMOJI_BUTTON_IMAGE_SIZE = (35, 35)

server_socket, client_id, recipient_id, recipient_public_key, recipient_aes_key = connect_and_register(SERVER_ADDRESS, SERVER_PORT)
dir_path = create_client_dir(client_id)

emoji_dict = create_emoji_dict()

file_types = (("PNG", "*.png"), ("JPEG", "*.jpg")) # only these file types will be

layout = [  # this is where the layout of the entire GUI is decribed
    [
        sg.Frame('',
                 layout=[[sg.Column(layout=[], key='-CHAT-', scrollable=True, expand_x=True, expand_y=True, vertical_scroll_only=True, pad=20, background_color=BACKGROUND_COLOR,)]],
                 size=(WINDOW_WIDTH, WINDOW_HEIGHT - 100),
                 background_color=BACKGROUND_COLOR)
    ],  # a scrollable column that will be updated with all the messages that are sent/received; it is surrounded by a simple frame, with no title
    [
        sg.In(enable_events=True, key='-FILE_PATH-', visible=False), # an invisible input element, that is used for storing the path an image before it is being sent;

        sg.Frame(' ', border_width=0,   #a frame surrounding the main controls of the app, described below:
                 layout=[
                     [
                         sg.In(size=(20, 1), enable_events=True, key="-SEND_TEXT-", font=FONT),                                                                                 # an input field where the user writes the text message that he wants to send to the other client
                         sg.Button('Send', enable_events=True, key='-SEND_BUTTON-', bind_return_key=True, font=FONT, button_color=BUTTON_COLOR),                                # message send button, bound to the 'enter' key
                         sg.FileBrowse('Image', target='-FILE_PATH-', file_types=file_types, key='-FILE_BROWSE-', font=FONT, button_color=BUTTON_COLOR, enable_events=True),    # a button that will open a browse window; in this window, the user cand browse for a PNG or JPG picture to send
                         sg.Button("\U0001F642", enable_events=True, key='-EMOJI_BUTTON-', font=FONT, button_color=BUTTON_COLOR),                                               # a toggle button used for hiding/showing the emoji frame
                     ]
                 ],
                 size=(400, 70),
                 element_justification='c'),

        sg.Frame("Emojis",     # a frame surrounding the emoji buttons
                 layout=[
                     [   # an array of emoji buttons, generated using the emoji dictionary created beforehand
                         sg.pin(sg.Button(key=emoji, image_filename=emoji_dict[emoji], image_size=EMOJI_BUTTON_IMAGE_SIZE, image_subsample=3, enable_events=True, button_color=BUTTON_COLOR, visible=True)) # an emoji button is places inside a pin element so that when hidden and then shown again, it will be in the same place
                         for emoji in emoji_dict.keys()
                     ]
                 ],
                 key='-EMOJI_FRAME-',
                 size=(500, 70),
                 element_justification='c')
    ]
]

window = sg.Window(f'{client_id}\'s chat window', layout, size=(WINDOW_WIDTH, WINDOW_HEIGHT), keep_on_top=True, finalize=True)  # the GUI window is rendered using the layout described above

received_msg_number = 0
received_msg_list = []
# these three are the shared variables between the main thread and the separate thread that receives messages (used for text messages)
received_msg_number_copy = 0 # when received_msg_number != received_msg_number_copy we know that a text message was received by the separate thread

received_images_number = 0
received_images_list = []
# these three are the shared variables between the main thread and the separate thread that receives messages (used for image messages)
received_images_number_copy = 0 # when received_msg_number != received_msg_number_copy we know that a image message was received by the separate thread

received_errors_number = 0
received_errors_list = []
received_errors_number_copy = 0

sent_images = 0     # variable used for counting the images sent, so that they will have an unique name when they are logged

t = Thread(target=rec_msg, args=(server_socket,))
t.daemon = True
t.start()

emojis_visible = True
# toggle variable for showing/hiding the emoji buttons

image_selected = False
# toggle variable that is set to True when an image is selected, so that the app will send that image and not a text message

while True:
    window['-CHAT-'].contents_changed()     # this method is called so that the scrollbar is updated when it is needed
                                            # this fixes the bug where, when there are a lot of messages and the scrollbar activates, the messages would be exchanged with delay
    event, values = window.read(timeout=100)
    if event == sg.TIMEOUT_KEY:                                                 # normally the while stalls until an event takes place, but since a separate thread can't trigger an event in the GUI in the main thread, a timeout of 100ms is set, so that each 100ms a while iteration passes
                                                                                # this is done so that each 100ms the main thread checks if something was written in the shared variables by the separate thread (meaning that a message was received)
        if received_msg_number != received_msg_number_copy:                     # when received_msg_number != received_msg_number_copy we know that a text message was received by the separate thread
            msg = received_msg_list[-1]
            print(f'{recipient_id}: {msg}')
            received_msg_number_copy = copy.copy(received_msg_number)  # the number of received text messages is updated
            if msg in emoji_dict.keys():
                img = Image.open(emoji_dict[msg])
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='PNG')
                show_image(recipient_id, img_bytes.getvalue(), 'l')
            else:
                show_message(recipient_id, msg, 'l')                                # the text message is displayed in the GUI

        elif received_images_number != received_images_number_copy:             # when received_msg_number != received_msg_number_copy we know that a image message was received by the separate thread
            print(f'{recipient_id}: sent image')
            received_images_number_copy = copy.copy(received_images_number)     # the number of received text messages is updated
            image = Image.open(io.BytesIO(received_images_list[-1]))
            compressed_image_bytes = io.BytesIO()
            image.thumbnail((500, 500))  # compress the image
            image.save(compressed_image_bytes, format='PNG')
            show_image(recipient_id, compressed_image_bytes.getvalue(), 'l')             # the text message is displayed in the GUI

        elif received_errors_number != received_errors_number_copy:
            received_errors_number_copy = copy.copy(received_errors_number)
            sg.popup(received_errors_list[-1])


    elif event == sg.WIN_CLOSED:
        break

    elif event == '-FILE_PATH-':                                                # since the image browser can't trigger an event, we check if there was a modification in the input field containing a file path to know if an image was selected for sending
        window['-FILE_BROWSE-'].update(button_color=BUTTON_COLOR)
        image_selected = True
        window['-SEND_BUTTON-'].update('Send Image')

    elif event == '-SEND_TEXT-':                                                # if an user selected an image but then changes his mind, he can write something in the input field for a text message, so that he won't send the image selected before
        image_selected = False
        window['-SEND_BUTTON-'].update('Send')

    elif event == '-SEND_BUTTON-':                                              # if the send button is pressed (or 'enter' key)
        if not image_selected:                                                  # case for text message
            msg = values['-SEND_TEXT-']
            if msg != '':                                                       # an empty message will not be sent
                window['-SEND_TEXT-'].update('')                                # clear input box when sending
                if len(msg) > 50:
                    sg.popup('Message limit is 50 characters!')                 # a popup window will be displayed when a message longer than 50 characters was written, since the chosen RSA library can only encrypt messages that are 53 bytes big
                else:
                    show_message(client_id, msg, 'r')                                           # the sent message is displayed in the GUI
                    log_message(f'{dir_path}/message_history_log.txt', client_id, msg)          # message history of a client contains the sent/received messages in chronological order
                    log_message(f'{dir_path}/{client_id}_sent_messages.txt', client_id, msg)    # sent messages are logged
                    send_msg(recipient_id, 'msg', client_id, msg, server_socket)                # and the message is sent to the other client

        else:                                                                               #case for sending images
            sent_images += 1
            image_selected = False
            window['-SEND_BUTTON-'].update('Send')
            if values['-FILE_PATH-'] != '':                                                 # check if somehow an empty path resulted when an images was chosen
                path = values['-FILE_PATH-']                                                # the path is extracted from the file path invisible input tool that only the file browser for images writes in
                window['-FILE_PATH-'].update('')
                if os.path.exists(path):                                                    # check if the path exists and is valid
                    image = Image.open(path)                                                # load the image in memory
                    image.thumbnail((1920,1080))                                            # compress image to FHD so it will fit in the socket
                    image_bytes = io.BytesIO()
                    image.save(image_bytes, format='PNG')                                   # image is converted to PNG and then to byte string

                    compressed_image_bytes = io.BytesIO()
                    image.thumbnail((500, 500))                                             # compress the image even more for thumbnail that will be displayed in the GUI
                    image.save(compressed_image_bytes, format='PNG')

                    send_msg(recipient_id, 'img', client_id, image_bytes.getvalue(),server_socket)   # the image is sent to the other client
                    show_image(client_id, compressed_image_bytes.getvalue(), 'r')                               # the image is displayed in the gui
                    image_path = f'{dir_path}/sent_images/image{sent_images}.png'
                    log_image(image_path, image_bytes.getvalue()) # image is logged in the client's directory of sent images
                    log_message(f'{dir_path}/message_history_log.txt', client_id, os.path.abspath(image_path))

    elif event == '-EMOJI_BUTTON-':
        if not emojis_visible:                                     # show emoji buttons
            for emoji in emoji_dict.keys():
                window[emoji].update(visible=True)
            window['-EMOJI_FRAME-'].update(visible=True)
            emojis_visible = True

        else:
            for emoji in emoji_dict.keys():                        # hide emoji buttons
                window[emoji].update(visible=False)
            window['-EMOJI_FRAME-'].update(visible=False)
            emojis_visible = False

    elif event in emoji_dict.keys():                               # if one of the emoji buttons is pressed, then it is sent exactly the same as an image
        sent_images += 1
        path = emoji_dict[event]
        if os.path.exists(path):                                   # check if path is valid
            image = Image.open(path)
            image_bytes = io.BytesIO()
            image.save(image_bytes, format='PNG')

            show_image(client_id, image_bytes.getvalue(), 'r')
            log_image(f'{dir_path}/sent_images/image{sent_images}.png', image_bytes.getvalue())
            # send_msg(recipient_id, 'img', client_id, image_bytes.getvalue(), server_socket)
            send_msg(recipient_id, 'msg', client_id, event, server_socket)

server_socket.close()
window.close()
