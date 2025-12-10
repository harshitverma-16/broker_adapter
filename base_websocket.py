import websocket
import threading
import json
import time
from abc import ABC, abstractmethod


class BaseWebSocket(ABC):

    def __init__(self, ws_url: str, auto_reconnect=True, ping_interval=20):
        self.ws_url = ws_url
        self.ws = None
        self.thread = None
        self.auto_reconnect = auto_reconnect
        self.ping_interval = ping_interval
        self.connected = False
        self._stop = False

    # ----------------------------------------------------------------------
    # Abstract Methods (Child must override)
    # ----------------------------------------------------------------------
    @abstractmethod
    def on_open(self):
        pass

    @abstractmethod
    def on_message(self, message):
        pass

    @abstractmethod
    def on_close(self):
        pass

    @abstractmethod
    def on_error(self, error):
        pass

    # ----------------------------------------------------------------------
    # Internal callbacks
    # ----------------------------------------------------------------------
    def _on_open(self, ws):
        self.connected = True
        self.on_open()

    def _on_message(self, ws, msg):
        self.on_message(msg)

    def _on_error(self, ws, err):
        self.on_error(err)

    def _on_close(self, ws, code=None, msg=None):
        self.connected = False
        self.on_close()

        if self.auto_reconnect and not self._stop:
            time.sleep(2)
            self.connect()  # reconnect

    # ----------------------------------------------------------------------
    # Connect
    # ----------------------------------------------------------------------
    def connect(self):
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )

        self.thread = threading.Thread(target=self.ws.run_forever, kwargs={
            "ping_interval": self.ping_interval
        })
        self.thread.daemon = True
        self.thread.start()

    # ----------------------------------------------------------------------
    # Send Data
    # ----------------------------------------------------------------------
    def send(self, data):
        if self.connected:
            if isinstance(data, dict):
                data = json.dumps(data)
            self.ws.send(data)

    # ----------------------------------------------------------------------
    # Close WS
    # ----------------------------------------------------------------------
    def close(self):
        self._stop = True
        if self.ws:
            self.ws.close()
        self.connected = False
