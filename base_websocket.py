# import websocket
# import threading
# import json
# import time
# from abc import ABC, abstractmethod


# class BaseWebSocket(ABC):

#     def __init__(self, ws_url: str, auto_reconnect=True, ping_interval=20):
#         self.ws_url = ws_url
#         self.ws = None
#         self.thread = None
#         self.auto_reconnect = auto_reconnect
#         self.ping_interval = ping_interval
#         self.connected = False
#         self._stop = False

#     # ============================================================
#     # ABSTRACT METHODS (Child must override)
#     # ============================================================

#     @abstractmethod
#     def on_open(self):
#         """Called when websocket connection opens."""
#         pass

#     @abstractmethod
#     def on_message(self, message):
#         """Called when a new websocket message is received."""
#         pass

#     @abstractmethod
#     def on_close(self):
#         """Called when websocket is closed."""
#         pass

#     @abstractmethod
#     def on_error(self, error):
#         """Called when websocket throws an error."""
#         pass

#     # ============================================================
#     # INTERNAL CALLBACKS
#     # ============================================================

#     def _on_open(self, ws):
#         self.connected = True
#         self.on_open()

#     def _on_message(self, ws, message):
#         self.on_message(message)

#     def _on_error(self, ws, error):
#         self.on_error(error)

#     def _on_close(self, ws, code=None, msg=None):
#         self.connected = False
#         self.on_close()

#         # Auto reconnect logic
#         if self.auto_reconnect and not self._stop:
#             time.sleep(2)
#             self.connect()

#     # ============================================================
#     # CONNECT
#     # ============================================================

#     def connect(self):
#         """Open websocket connection."""
#         self._stop = False

#         self.ws = websocket.WebSocketApp(
#             self.ws_url,
#             on_open=self._on_open,
#             on_message=self._on_message,
#             on_error=self._on_error,
#             on_close=self._on_close
#         )

#         self.thread = threading.Thread(
#             target=self.ws.run_forever,
#             kwargs={"ping_interval": self.ping_interval}
#         )
#         self.thread.daemon = True
#         self.thread.start()

#     # ============================================================
#     # SEND
#     # ============================================================

#     def send(self, data):
#         """Send data to websocket."""
#         if not self.connected:
#             return

#         if isinstance(data, dict):
#             data = json.dumps(data)

#         self.ws.send(data)

#     # ============================================================
#     # CLOSE
#     # ============================================================

#     def close(self):
#         """Manually close websocket."""
#         self._stop = True
#         self.connected = False

#         if self.ws:
#             self.ws.close()
