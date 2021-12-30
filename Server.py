import socket
from threading import Thread
import pickle


SERVER_ADDRESS = '127.0.0.1'
SERVER_PORT = 6001
CLIENT_NB = 5
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
            print(msg)
            if msg['type'] == 'id':
                client_id = msg['body']
                if client_id == '':
                    send_msg('', 'register', 'Invalid ID: empty.', conn)

                elif client_id in client_dict:
                    send_msg('', 'register', 'Invalid ID: already taken.', conn)
                else:

                    confirmation = f'Welcome {client_id}!'
                    send_msg(client_id, 'register_ok', confirmation, conn)
                    formatted_public_key = conn.recv(4096)
                    client_dict[client_id] = (conn, formatted_public_key)

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
            conn.close()
            exit()
        else:
            msg = pickle.loads(data)
            # print(' [THREAD] Message from client:', msg)
            send_msg_pickle(msg, client_dict[recipient_id][0])

    print(' [THREAD] Closing connection...')
    conn.close()
    exit()


while True:
    client, address = socket.accept()
    print('Received connection from:', address)
    t = Thread(target=handle_client, args=(client,))
    t.daemon = True
    t.start()
