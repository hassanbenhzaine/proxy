import socket
import threading
import random
import time

# Constants
SERVER_PORT = 10000
BUFFER_SIZE = 4096
RETRANSMISSION_TIMEOUT = 5  # Increased timeout to 5 seconds
SOURCE_PORT_RANGE = (20000, 30000)  # Specify your range here
POOL_SIZE = 10  # Number of sockets in the pool

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

def handle_client(client_data, client_address, socket_pool):
    try:
        packet_id = client_data[:4]
        
        # Update the delimiter to '|'
        data_parts = client_data[4:].split(b'|', 1)  # Split only once
        
        if len(data_parts) < 2:
            raise ValueError("Malformed packet received")
        
        dest_ip = data_parts[0].decode()
        dest_port_data = data_parts[1].split(b':', 1)  # Split on ':' to separate port from payload
        
        if len(dest_port_data) < 2:
            raise ValueError("Malformed packet: missing port or payload")
        
        # Convert destination port
        dest_port = int(dest_port_data[0])  # Here we expect the port as bytes
        payload = dest_port_data[1]  # This is the actual payload

        # Send acknowledgment of receipt to the client
        print(f"Sending ACK for packet ID: {packet_id.hex()} to {client_address}")
        server_socket.sendto(packet_id, client_address)

        # Get a socket from the pool
        temp_socket = socket_pool.get_socket()

        try:
            # Send to destination
            temp_socket.sendto(payload, (dest_ip, dest_port))

            # Receive response from destination
            response, _ = temp_socket.recvfrom(BUFFER_SIZE)

            # Send response back to client with packet ID for acknowledgment
            response_packet = packet_id + response
            while True:
                server_socket.sendto(response_packet, client_address)
                start_time = time.time()
                try:
                    ack, _ = server_socket.recvfrom(BUFFER_SIZE)
                    if ack == packet_id:
                        print(f"ACK received for packet ID: {packet_id.hex()}")
                        break  # Acknowledgment received
                except socket.timeout:
                    if time.time() - start_time >= RETRANSMISSION_TIMEOUT:
                        print(f"Timeout waiting for ACK for packet ID: {packet_id.hex()}, resending response...")
                        continue
        except socket.timeout:
            print("Timeout waiting for response from destination.")
        finally:
            socket_pool.return_socket(temp_socket)
    except Exception as e:
        print(f"Error handling client data: {e}")

def main():
    global server_socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.settimeout(RETRANSMISSION_TIMEOUT)
    server_socket.bind(('0.0.0.0', SERVER_PORT))
    print(f"Server listening on port {SERVER_PORT}")

    socket_pool = SocketPool(POOL_SIZE, SOURCE_PORT_RANGE)

    while True:
        try:
            client_data, client_address = server_socket.recvfrom(BUFFER_SIZE)
            client_handler = threading.Thread(target=handle_client, args=(client_data, client_address, socket_pool))
            client_handler.start()
        except Exception as e:
            print(f"Error receiving data from client: {e}")

if __name__ == "__main__":
    main()
