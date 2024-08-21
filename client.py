import socket
import threading
import random
import time
import uuid

# Constants
LOCAL_PROXY_IP = '127.0.0.1'
LOCAL_PROXY_PORT = 1080
REMOTE_SERVER_IP = '13.39.111.200'
REMOTE_SERVER_PORT = 10000
BUFFER_SIZE = 4096
RETRANSMISSION_TIMEOUT = 5  # seconds
SOURCE_PORT_RANGE = (20000, 30000)  # Specify your range here
POOL_SIZE = 50  # Number of sockets in the pool

class SocketPool:
    def __init__(self, size, port_range):
        self.size = size
        self.port_range = port_range
        self.sockets = [self.create_socket() for _ in range(size)]
        self.lock = threading.Lock()

    def create_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('', random.randint(*self.port_range)))
        return sock

    def get_socket(self):
        with self.lock:
            if self.sockets:
                return self.sockets.pop()
            else:
                return self.create_socket()

    def return_socket(self, sock):
        with self.lock:
            self.sockets.append(sock)

def receive_from_server(udp_socket, client_socket, address_map, lock):
    while True:
        try:
            response, _ = udp_socket.recvfrom(BUFFER_SIZE)
            packet_id = response[:4]
            payload = response[4:]
            with lock:
                if packet_id in address_map:
                    client_socket.send(payload)
                    del address_map[packet_id]
        except socket.timeout:
            continue
        except Exception as e:
            print(f"Error receiving from server: {e}")
            break

def handle_client(client_socket, socket_pool):
    try:
        client_socket.recv(BUFFER_SIZE)
        client_socket.send(b'\x05\x00')  # SOCKS5, no auth

        request = client_socket.recv(BUFFER_SIZE)
        if request[1] == 1:  # CONNECT command
            dest_ip = socket.inet_ntoa(request[4:8])
            dest_port = int.from_bytes(request[8:10], 'big')

            client_socket.send(b'\x05\x00\x00\x01' + socket.inet_aton(LOCAL_PROXY_IP) + (LOCAL_PROXY_PORT).to_bytes(2, 'big'))

            # Create a pool of UDP sockets for this client session
            udp_socket = socket_pool.get_socket()
            udp_socket.settimeout(RETRANSMISSION_TIMEOUT)

            address_map = {}
            lock = threading.Lock()
            threading.Thread(target=receive_from_server, args=(udp_socket, client_socket, address_map, lock)).start()

            while True:
                data = client_socket.recv(BUFFER_SIZE)
                if not data:
                    break

                # Generate a unique packet ID using UUID
                packet_id = uuid.uuid4().bytes[:4]
                # Client: Use '|' as the delimiter instead of ':'
                packet = packet_id + f"{dest_ip}|{dest_port}".encode() + b':' + data

                with lock:
                    address_map[packet_id] = packet

                while packet_id in address_map:
                    udp_socket.sendto(packet, (REMOTE_SERVER_IP, REMOTE_SERVER_PORT))
                    start_time = time.time()
                    try:
                        ack, _ = udp_socket.recvfrom(BUFFER_SIZE)
                        if ack == packet_id:
                            print(f"Received ACK for packet ID: {packet_id.hex()}")
                            with lock:
                                address_map.pop(packet_id, None)
                    except socket.timeout:
                        if time.time() - start_time >= RETRANSMISSION_TIMEOUT:
                            print(f"Timeout waiting for ACK for packet ID: {packet_id.hex()}, retransmitting...")
                            continue
                    except Exception as e:
                        print(f"Error during acknowledgment: {e}")
                        break

            socket_pool.return_socket(udp_socket)
    except Exception as e:
        print(f"Error handling client: {e}")
    finally:
        client_socket.close()

def start_proxy(socket_pool):
    proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow address reuse
    proxy_socket.bind((LOCAL_PROXY_IP, LOCAL_PROXY_PORT))  # Bind the proxy to the specified local port
    proxy_socket.listen(5)  # Listen for incoming connections
    print(f"Local SOCKS5 proxy listening on port {LOCAL_PROXY_PORT}")

    while True:
        client_socket, addr = proxy_socket.accept()  # Accept a new client connection
        print(f"Accepted connection from {addr}")
        client_handler = threading.Thread(target=handle_client, args=(client_socket, socket_pool))
        client_handler.start()  # Start a new thread to handle the client

if __name__ == "__main__":
    # Initialize the socket pool for client usage
    client_socket_pool = SocketPool(POOL_SIZE, SOURCE_PORT_RANGE)  # Create a socket pool
    start_proxy(client_socket_pool)  # Start the SOCKS5 proxy server