import socket
import selectors

def handle_connection(sock, mask):
    conn, addr = sock.accept()  # Accept the connection
    print(f"Accepted connection from {addr}")
    data = conn.recv(1024)  # Receive data from the client
    print(f"Received data from {addr}: {data.decode('utf-8')}")
    # conn.send(b"Hello from server!")  # Send a response
    conn.close()  # Close the connection

def main():
    selector = selectors.DefaultSelector()

    for port in range(0, 65536):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('0.0.0.0', port))
        sock.listen(5)  # Start listening for incoming connections
        sock.setblocking(False)
        selector.register(sock, selectors.EVENT_READ, handle_connection)
        # print(f"Listening on TCP port {port}")

    while True:
        events = selector.select(timeout=None)  # Block until an event happens
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)

if __name__ == "__main__":
    main()
