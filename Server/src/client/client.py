import argparse
import socket
import sys
import os
import threading

BUFFER_SIZE = 2**12
ENCODING = "UTF-8"

# Server details
SERVER_IP = "127.0.0.1"  
PORT = 10005  
ENCODING = "UTF-8"

# CLI Argument Parser
def parse_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", type=str, default=SERVER_IP, help="Address to use, by default uses docker internal")
    return parser.parse_args()

def receive_messages(client_socket):
    while True:
        try:
            response = client_socket.recv(1024).decode(ENCODING).strip()
            if not response:
                print("\nConnection closed by server.")
                break
            print(f"[Server]: {response}\n> ", end="", flush=True)  # Keep input prompt visible
        except ConnectionResetError:
            print("\nERROR: Connection lost.")
            break
        except Exception as e:
            print(f"\nERROR: {e}")
            break
    os._exit(0)

def test_client():
    """Connects to the chat server and sends a HELLO message."""
    try:
        # Create a socket to connect to the server
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((SERVER_IP, PORT))
        print(f"Connected to server at {SERVER_IP}:{PORT}")

        # Start a separate thread to handle incoming messages
        receive_thread = threading.Thread(target=receive_messages, args=(client_socket,), daemon=True)
        receive_thread.start()

        # Interactive loop for sending messages
        while True:
            message = input("")  # Get input from user

            if not message.strip():
                continue  # Ignore empty messages

            client_socket.sendall(f"{message}\n".encode(ENCODING))

    except ConnectionRefusedError:
        print("ERROR: Could not connect to server. Is the server running?")
    except Exception as e:
        print(f"ERROR: {e}")
    except KeyboardInterrupt:
        print("Exiting...")
        sys.exit(0)

if __name__ == "__main__":
    args = parse_cli()
    SERVER_IP = args.i
    test_client()
