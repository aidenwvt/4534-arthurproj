import threading
from .gui import guiMain
from .server import serverMain

if __name__ == "__main__":
    server_thread = threading.Thread(target=serverMain, daemon=True)
    server_thread.start()

    guiMain()