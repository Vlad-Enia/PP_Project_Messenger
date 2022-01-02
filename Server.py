import socket
from threading import Thread
import pickle
import os


SERVER_ADDRESS = '127.0.0.1'
SERVER_PORT = 6001
CLIENT_NB = 5
MESSAGE_LOG_FILENAME = 'message_history_log.txt'
client_dict = dict()
socket = socket.socket()
socket.bind((SERVER_ADDRESS, SERVER_PORT))
socket.listen(CLIENT_NB)


def send_msg(recipient, msg_type, msg, recipient_socket):
    d = {
        'type': msg_type,
        'sender': 'server',
        'recipient': recipient,
        'body': msg
    }
    recipient_socket.send(pickle.dumps(d))


def send_msg_pickle(msg_pickle, recipient_socket):
    recipient_socket.send(pickle.dumps(msg_pickle))


def handle_client(conn):
    send_msg('', 'register', 'Hello! You need to register first with an unique id.', conn)
    client_id = ''
    while conn not in client_dict.values():
        try:
            data = conn.recv(4096)
        except Exception as e:
            print(' [THREAD] Connection interrupted...')
            conn.close()
            exit()
        else:
            msg = pickle.loads(data)
            # print(msg)
            if msg['type'] == 'id':
                client_id = msg['body']
                if client_id == '':
                    send_msg('', 'register', 'Invalid ID: empty.', conn)

                elif client_id in client_dict:
                    send_msg('', 'register', 'Invalid ID: already taken.', conn)
                else:

                    confirmation = f'Welcome {client_id}! Please wait for another client to join.'
                    send_msg(client_id, 'register_ok', confirmation, conn)
                    msg = pickle.loads(conn.recv(4096))
                    print("MESSAGE", msg)
                    if msg['type'] == 'pbkey':
                        client_dict[client_id] = (conn, msg['body'])
                    break
    print(f' [THREAD] Client {client_id} registered successfully!')
    while len(client_dict) < 2:
        pass
    recipient_id = ''
    for cl in client_dict.keys():
        if cl != client_id:
            send_msg(client_id, 'recipient_id', cl, conn)
            conn.send(client_dict[cl][1])
            recipient_id = cl
            break
    while True:
        try:
            data = conn.recv(4096)
        except Exception as e:
            print(' [THREAD] Connection interrupted...')
            break
        else:
            msg = pickle.loads(data)
            # print('MESSAGE:',msg)
            # log_message(data['body'])
            send_msg_pickle(msg, client_dict[recipient_id][0])

    print(' [THREAD] Closing connection...')
    client_dict.pop(client_id, None)
    conn.close()
    exit()



while True:
    client, address = socket.accept()
    print('Received connection from:', address)
    t = Thread(target=handle_client, args=(client,))
    t.daemon = True
    t.start()
