import argparse
import logging
import os
import selectors
import socket
import sys
import multiprocessing
from serverDatabase import *

BUFFER_SIZE = 2**12
ENCODING = "UTF-8"
LOCAL_IP = "127.0.0.1"
LOCAL_PORT = 10005
SELECT_TIMEOUT_SECONDS = 1
DEFAULT_MAX_CLIENTS = 50

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
    # drinkDatabase.displayDatabase()

class ClientHandler:
    def __init__(self, peer_socket, peer_address):
        self._peer_socket = peer_socket
        self._peer_address = peer_address
        
    def run(self):
        # need to initialize the logging framework in this process
        initLogging()
        logger.info(f"Handling client {self._peer_address}")
        with self._peer_socket:
            logger.info(f"Connected to {self._peer_address}")
            try:
                self._peer_socket.send("ready\r\n".encode(ENCODING))
                while data := self._peer_socket.recv(BUFFER_SIZE).strip():
                    logger.info(f"Received from client {self._peer_address}: {data}")
                    retrievedDrink = drinkDatabase.retrieveDrink(data)
                    jsonString = json.dumps(retrievedDrink)
                    self._peer_socket.send(jsonString.encode(ENCODING))

            except OSError as err:
                logger.error(f"Error communicating with {self._peer_address}: {err}")
        
            except KeyboardInterrupt:
                logger.info("Shutting down")

            logger.info(f"Disconnected from {self._peer_address}")
        
class Server:
    def __init__(self, port):
        self.port = port
        self.max_workers = DEFAULT_MAX_CLIENTS
        self._selector = selectors.DefaultSelector()
        self._workers: set[multiprocessing.Process] = set()

    def _rejectClient(self, peer_socket, peer_address):
        try:
            peer_socket.send("Closing connection\r\n".encode(ENCODING))
            peer_socket.close()
        except OSError as err:
            logger.warning(f"Failed to close client {peer_address} socket: {err}")

    def _acceptClient(self, server_socket):
        peer_socket, peer_address = server_socket.accept()
        if len(self._workers) >= self.max_workers:
            self._rejectClient(peer_socket, peer_address)
            return
        
        handler = ClientHandler(peer_socket, peer_address)
        worker = multiprocessing.Process(target=handler.run)
        self._workers.add(worker)
        worker.start()
        logger.info(f"Started process {worker.ident} for client {peer_address}")

    def _openListener(self):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)      
            server_socket.bind((LOCAL_IP, self.port))
            server_socket.listen()
            self._selector.register(server_socket, selectors.EVENT_READ, self._acceptClient)
        except OSError as err:
            logger.error(f"Cannot listen on port {self.port}: {err}")
            raise SystemExit(1)

        logger.info(f"Listening on port {self.port}")

    def _reapDeadChildren(self):
        logger.debug("Reaping dead children")
        for worker in tuple(self._workers):
            if not worker.is_alive():
                self._workers.discard(worker)
                if worker.exitcode == 0:
                    logger.info(f"Process {worker.ident} terminated normally")
                else:
                    logger.warning(f"Process {worker.ident} terminated with exit code {abs(worker.exitcode)}")
                worker.close()
        
    def run(self):
        self._openListener()
        try:
            while True:
                for selectable, _ in self._selector.select(SELECT_TIMEOUT_SECONDS):
                    callback_fn = selectable.data
                    callback_fn(selectable.fileobj)
                
                self._reapDeadChildren()
        
        except KeyboardInterrupt:
            logger.info("Shutting down")   
            os._exit(0) 

if __name__ == "__main__":
    initLogging()
    initDatabase()
    args = parseCLI()
    server = Server(args.port)
    server.run()
