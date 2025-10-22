import argparse
import logging
import os
import selectors
import socket
import sys
import time
import threading
from .serverDatabase import *

BUFFER_SIZE = 2**12
ENCODING = "UTF-8"
LOCAL_IP = "127.0.0.1"
LOCAL_PORT = 10005

logger = logging.getLogger(__name__)

def initLogging():
    logging.basicConfig(stream=sys.stdout, level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(process)d: %(message)s")

def parseCLI():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=LOCAL_PORT, help="port on which to listen for connections")
    return parser.parse_args()

def initDatabase():
    drinkDatabase.clearDatabase()
    mixedDrinks.initializeMixedDrinks()
    simpleDrinks.initializeSimpleDrinks()

class ClientHandler:
    def __init__(self, peer_socket, peer_address):
        self.peer_socket = peer_socket
        self._peer_address = peer_address
        
    def run(self):
        initLogging()
        logger.info(f"Handling client {self._peer_address}")
        with self.peer_socket:
            logger.info(f"Connected to {self._peer_address}")
            try:
                self.peer_socket.send("ready\r\n".encode(ENCODING))
                while data := self.peer_socket.recv(BUFFER_SIZE).strip():
                    logger.info(f"Received from client {self._peer_address}: {data}")
                    retrievedDrink = drinkDatabase.retrieveDrink(data)
                    if (retrievedDrink != 0):
                        jsonString = json.dumps(retrievedDrink)
                        self.peer_socket.send(jsonString.encode(ENCODING))
                    else:
                        self.peer_socket.send("Drink not found".encode(ENCODING))


            except OSError as err:
                logger.error(f"Error communicating with {self._peer_address}: {err}")
        
            except KeyboardInterrupt:
                logger.info("Shutting down")

            logger.info(f"Disconnected from {self._peer_address}")

class QueueHandler:
    def __init__(self, peer_socket, peer_address):
        self.peer_socket = peer_socket
        self._peer_address = peer_address

    def run(self):
        while True:
            logger.error("Test")
            queuedItem = Queue.getQueue()
            logger.info(queuedItem)
            if queuedItem:
                self.peer_socket.send(json.dumps(queuedItem).encode(ENCODING))
                logger.info(f"Sent queued item to {self._peer_address}")
            time.sleep(5)
        
class Server:
    def __init__(self, port):
        self.port = port
        self.server_socket = None

    def _openListener(self):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)      
            server_socket.bind((LOCAL_IP, self.port))
            server_socket.listen()
            self.server_socket = server_socket
        except OSError as err:
            logger.error(f"Cannot listen on port {self.port}: {err}")
            raise SystemExit(1)

        logger.info(f"Listening on port {self.port}")

    def run(self):
        self._openListener()
        try:
            while True:
                peer_socket, peer_address = self.server_socket.accept()
                
                handler = ClientHandler(peer_socket, peer_address)
                queueHandler = QueueHandler(peer_socket, peer_address)
                clientThread = threading.Thread(target=handler.run, daemon=True)
                queueThread = threading.Thread(target=queueHandler.run, daemon=True)

                clientThread.start()
                queueThread.start()
        
        except KeyboardInterrupt:
            logger.info("Shutting down\r\n")   
            raise SystemExit(1)

def serverMain():
    initLogging()
    initDatabase()
    args = parseCLI()
    server = Server(args.port)
    server.run()