import socket
import pickle
import rsa
from threading import Thread

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
        log_message(f'{client_id}_received_messages.txt', sender, decrypted_message)
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
    message = pickle.loads(sock.recv(4096))
    while message['type'] == 'register':
        print('Server:', message['body'])
        cl_id = input('ID: ')
        send_msg('server', 'id', cl_id, cl_id, sock)
        message = pickle.loads(sock.recv(4096))
    print('Server:', message['body'])
    formatted_public_key = public_key.save_pkcs1(format='DER')
    # sock.send(formatted_public_key)
    send_msg('server', 'pbkey', cl_id, formatted_public_key, sock)
    # message = pickle.loads(sock.recv(4096))
    # print('Server:', message['body'])
    return sock, cl_id


def log_message(filename, sender, message):
    f = open(filename, 'a')
    f.write(f'{sender}: {message}\n')
    f.close()


server_socket, client_id = connect_and_register(SERVER_ADDRESS, SERVER_PORT)

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
    log_message('message_history_log.txt',client_id, msg)
    log_message(f'{client_id}_sent_messages.txt', client_id, msg)
    msg_encrypted = rsa.encrypt(msg.encode('utf8'), recipient_public_key)
    send_msg(recipient_id, 'msg', client_id, msg_encrypted, server_socket)
