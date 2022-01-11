import socket
from threading import Thread
import pickle

SERVER_ADDRESS = '127.0.0.1'
SERVER_PORT = 6001
BUFFER_SIZE = 4096000
CLIENT_NB = 2
client_dict = dict()            # a dictionary used for storing each client's RSA public key; the dictionary keys are client IDs;
socket = socket.socket()
socket.bind((SERVER_ADDRESS, SERVER_PORT))
socket.listen(CLIENT_NB)


def send_msg(recipient, msg_type, msg, recipient_socket):
    """
    Method used for sending a message from the server to a client.
    A dictionary containing the following information is being serialized and then sent:
    :param recipient: recipient ID
    :param msg_type: message type
    :param msg: message
    :param recipient_socket: socket used for communication with that client
    """
    d = {
        'type': msg_type,
        'sender': 'server',
        'recipient': recipient,
        'body': msg
    }
    try:
        recipient_socket.send(pickle.dumps(d))
    except Exception as e:
        print(f' [THREAD] Connection interrupted... {recipient} disconnected')
        client_dict.pop(recipient)
        recipient_socket.close()



def forward_message(msg_pickle, recipient_socket):
    """
    Method used by the server to forward a message received by a client to the other client.
    :param msg_pickle: message sent by the sender, serialized
    :param recipient_socket: socket used for communication with the recipient
    :return:
    """

    d = pickle.loads(msg_pickle)

    recipient = d['recipient']

    try:
        recipient_socket.send(msg_pickle)
    except Exception as e:
        print(f' [THREAD] Connection interrupted... {recipient} disconnected')
        client_dict.pop(recipient)
        recipient_socket.close()


def handle_client(conn):
    """
    When a connection request is received from a client, this method will launch in a separate thread.
    It is used for registering the clients and for sending to a client the other client's ID and RSA public key.
    :param conn:
    :return:
    """
    send_msg('', 'register', 'Hello! You need to register first with an unique id.', conn)          # when a connection request is received from a client, a confirmation message is sent
    client_id = ''

    while conn not in client_dict.values():                         # a new client connects
        try:
            data = conn.recv(BUFFER_SIZE)
        except Exception as e:
            print(' [THREAD] Connection interrupted...')

            conn.close()
            exit()

        else:
            msg = pickle.loads(data)
            if msg['type'] == 'id':
                client_id = msg['body']                                                                 # and sends his id
                if client_id == '':                                                                     # the servers checks if it is either empty
                    send_msg('', 'register', 'Invalid ID: empty.', conn)
                elif client_id in client_dict:
                    send_msg('', 'register', 'Invalid ID: already taken.', conn)                        # or already taken

                else:
                    confirmation = f'Welcome {client_id}! Please wait for another client to join.'      # server sends confirmation of succesful registration to the client
                    send_msg(client_id, 'register_ok', confirmation, conn)

                    msg = pickle.loads(conn.recv(BUFFER_SIZE))
                    print("MESSAGE", msg)

                    if msg['type'] == 'pbkey':                                                          # the client then sends his public RSA key to be stored in the dictionary
                        client_dict[client_id] = (conn, msg['body'])
                    break

    print(f' [THREAD] Client {client_id} registered successfully!')

    while len(client_dict) < 2:                                                                         # the server waits for the other client to connect
        pass

    recipient_id = ''
    for cl in client_dict.keys():                                                                       # if the other client connected, the servers sends his id and public RSA key to the first client
        if cl != client_id:
            send_msg(client_id, 'recipient_id', cl, conn)
            conn.send(client_dict[cl][1])
            recipient_id = cl
            break                                                                                       #decomment for more clients

    while True:                                                                                         # after that, the server is ready to forward messages between clients
        try:
            msg = conn.recv(BUFFER_SIZE)
        except Exception as e:
            print(f' [THREAD] Connection interrupted... {client_id} disconnected')
            send_msg(recipient_id, 'error', f'{client_id} disconnected', client_dict[recipient_id][0])
            conn.close()
            break
        else:
            forward_message(msg, client_dict[recipient_id][0])

    print(' [THREAD] Closing connection...')
    client_dict.pop(client_id, None)
    conn.close()
    exit()


while True:
    client, address = socket.accept()                               # when a connection request is received from a client
    print('Received connection from:', address)
    t = Thread(target=handle_client, args=(client,))                # a thread that will handel that client is started
    t.daemon = True
    t.start()
