import socket
import json
from threading import Thread

SERVER_ADDRESS = '127.0.0.1'
SERVER_PORT = 6000
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
    recipient_socket.send(json.dumps(d).encode())


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
            msg = json.loads(data)
            print(msg)
            if msg['type'] == 'id':
                client_id = msg['body']
                if client_id == '':
                    send_msg('', 'register', 'Invalid ID: empty.', conn)

                elif client_id in client_dict:
                    send_msg('', 'register', 'Invalid ID: already taken.', conn)
                else:
                    client_dict[client_id] = conn
                    confirmation = f'Welcome {client_id}!'
                    send_msg(client_id, 'register_ok', confirmation, conn)
                    break
    print(f' [THREAD] Client {client_id} registered successfully!')
    while True:
        try:
            data = conn.recv(4096)
        except Exception as e:
            print(' [THREAD] Connection interrupted...')
            conn.close()
            exit()
        else:
            msg = json.loads(data)
            print(' [THREAD] Message from client:', msg)

    print(' [THREAD] Closing connection...')
    conn.close()
    exit()


while True:
    client, address = socket.accept()
    print('Received connection from:', address)
    t = Thread(target=handle_client, args=(client,))
    t.daemon = True
    t.start()
