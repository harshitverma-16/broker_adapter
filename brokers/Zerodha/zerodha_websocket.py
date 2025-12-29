# import asyncio
# import json
# import struct
# import signal
# import websockets
# from typing import List, Optional
# from utils.redis_publisher import RedisPublisher

# WS_URL = "wss://ws.kite.trade"

# MODE_LTP = "ltp"
# MODE_QUOTE = "quote"
# MODE_FULL = "full"


# class ZerodhaWebSocket:
#     def __init__(self, api_key: str, access_token: str):
#         self.url = f"{WS_URL}?api_key={api_key}&access_token={access_token}"
#         self.ws: Optional[websockets.WebSocketClientProtocol] = None

#         self.connected = asyncio.Event()
#         self.should_run = True

#         self.tokens: List[int] = []
#         self.mode = MODE_LTP

#         self.redis = RedisPublisher()


#     # Start websocket (auto reconnect)

#     async def start(self):
#         while self.should_run:
#             try:
#                 await self.connect()
#                 await self.listen()
#             except Exception as exc:
#                 print(f"WebSocket error: {exc}")
#             finally:
#                 self.connected.clear()
#                 if self.ws:
#                     await self.ws.close()
#                 await asyncio.sleep(3)


#     # Connect

#     async def connect(self):
#         self.ws = await websockets.connect(
#             self.url,
#             ping_interval=20,
#             ping_timeout=10,
#             compression=None
#         )
#         self.connected.set()

#         if self.tokens:
#             await self.subscribe(self.tokens, self.mode)


#     # Subscribe

#     async def subscribe(self, tokens: List[int], mode=MODE_LTP):
#         await self.connected.wait()

#         self.tokens = tokens
#         self.mode = mode

#         await self.ws.send(json.dumps({
#             "a": "subscribe",
#             "v": tokens
#         }))

#         await self.ws.send(json.dumps({
#             "a": "mode",
#             "v": [mode, tokens]
#         }))


#     # Listen

#     async def listen(self):
#         async for message in self.ws:
#             if isinstance(message, bytes):
#                 for tick in self.parse_binary(message):
#                     if tick:
#                         self.on_tick(tick)
#             else:
#                 self.handle_text(message)


#     # Handle text messages

#     def handle_text(self, message: str):
#         try:
#             data = json.loads(message)
#             if data.get("type") == "error":
#                 print("WebSocket error:", data)
#         except json.JSONDecodeError:
#             pass


#     # Redis publish hook

#     def on_tick(self, tick: dict):
#         """
#         Publish every tick to Redis without blocking the loop
#         """
#         # Get the running event loop
#         try:
#             loop = asyncio.get_running_loop()
#             # Run the synchronous redis publish in a separate thread
#             loop.run_in_executor(None, self.redis.publish, "zerodha.ticks", tick)
#         except RuntimeError:
#             # Fallback if no loop is running (e.g., during testing)
#             self.redis.publish("zerodha.ticks", tick)


#     # Binary parsing

#     def parse_binary(self, packet: bytes):
#         ticks = []
#         offset = 0

#         if len(packet) < 2:
#             return ticks

#         num_packets = struct.unpack_from(">H", packet, offset)[0]
#         offset += 2

#         for _ in range(num_packets):
#             if offset + 2 > len(packet):
#                 break

#             pkt_len = struct.unpack_from(">H", packet, offset)[0]
#             offset += 2

#             pkt = packet[offset: offset + pkt_len]
#             offset += pkt_len

#             tick = self.parse_tick(pkt)
#             ticks.append(tick)

#         return ticks

#     def parse_tick(self, pkt: bytes):
#         if len(pkt) < 8:
#             return None

#         instrument_token = struct.unpack_from(">I", pkt, 0)[0]
#         last_price = struct.unpack_from(">I", pkt, 4)[0] / 100

#         if len(pkt) == 8:
#             return {
#                 "instrument_token": instrument_token,
#                 "mode": "LTP",
#                 "last_price": last_price
#             }

#         if len(pkt) == 44:
#             volume = struct.unpack_from(">I", pkt, 8)[0]
#             return {
#                 "instrument_token": instrument_token,
#                 "mode": "QUOTE",
#                 "last_price": last_price,
#                 "volume": volume
#             }

#         if len(pkt) == 184:
#             volume = struct.unpack_from(">I", pkt, 8)[0]
#             oi = struct.unpack_from(">I", pkt, 12)[0]
#             return {
#                 "instrument_token": instrument_token,
#                 "mode": "FULL",
#                 "last_price": last_price,
#                 "volume": volume,
#                 "open_interest": oi
#             }

#         return None


#     # Stop

#     async def stop(self):
#         self.should_run = False
#         if self.ws:
#             await self.ws.close()

import time
import json
import logging
import redis
from kiteconnect import KiteTicker
from api.auth import ZerodhaAuthAPI

logging.basicConfig(level=logging.INFO)

# ---------------- CONFIG ----------------
API_KEY = "e2zjycwhnc7xknxp"
API_SECRET = "jvo244jvuzepmzhkhiucs4pd6hpmdpc4"
REDIRECT_URL = "http://localhost"
USER_ID = "SEJ657"

# Redis
r = redis.Redis(host="localhost", port=6379, decode_responses=True)

# ---------------- LOGIN ----------------
auth = ZerodhaAuthAPI(API_KEY, API_SECRET, REDIRECT_URL)

print("\nOpen this URL to login:")
print(auth.generate_login_url())

request_token = input("\nPaste request_token: ").strip()
access_token = auth.exchange_token(request_token)
print(" Access token generated")

# ---------------- WEBSOCKET ----------------
ws_token = f"{access_token}&user_id={USER_ID}"
kws = KiteTicker(API_KEY, ws_token)

# Keep track of connection status
is_connected = False

# ---------- CALLBACKS ----------
def on_connect(ws, response):
    global is_connected
    logging.info(" WebSocket connected")
    is_connected = True
    # Example: Subscribe to sample instruments after connection
    # kws.subscribe([738561, 5633])  # Replace with real instrument_tokens
    # kws.set_mode("full", [738561, 5633])

def on_close(ws, code, reason):
    global is_connected
    logging.warning(f" WebSocket closed: {code} {reason}")
    is_connected = False
    logging.info("Reconnecting in 3 seconds...")
    time.sleep(3)
    kws.connect(threaded=True)

def on_error(ws, code, reason):
    logging.error(f" WebSocket error: {code} {reason}")

def on_order_update(ws, order):
    logging.info(f" Order Update: {order}")
    event_map = {
        "OPEN": "ORDER_ACCEPTED",
        "COMPLETE": "ORDER_TRADED",
        "CANCELLED": "ORDER_CANCELLED",
        "REJECTED": "ORDER_REJECTED"
    }
    payload = {
        "event": event_map.get(order["status"], "ORDER_UPDATED"),
        "order_id": order["order_id"],
        "current_status": order["status"],
        "details": order
    }
    r.publish("zerodha.orders", json.dumps(payload))
    logging.info(f" Published {payload['event']}")

def on_ticks(ws, ticks):
    logging.debug(f" Tick Update: {ticks}")
    payload = {
        "event": "TICK_UPDATE",
        "ticks": ticks
    }
    r.publish("zerodha.ticks", json.dumps(payload))

# ---------- ASSIGN CALLBACKS ----------
kws.on_connect = on_connect
kws.on_close = on_close
kws.on_error = on_error
kws.on_order_update = on_order_update
kws.on_ticks = on_ticks

# ---------- UTILITY FUNCTIONS ----------
def subscribe_instruments(instruments, mode="full"):
    if not is_connected:
        logging.error("Not connected yet. Cannot subscribe.")
        return
    logging.info(f"Subscribing: {instruments} in {mode} mode")
    kws.subscribe(instruments)
    kws.set_mode(mode, instruments)

def unsubscribe_instruments(instruments):
    if not is_connected:
        logging.error("Not connected yet. Cannot unsubscribe.")
        return
    logging.info(f"Unsubscribing: {instruments}")
    kws.unsubscribe(instruments)

# ---------- START WEBSOCKET ----------
kws.connect(threaded=True)

# Keep main thread alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    logging.info("Stopping WebSocket...")
    kws.stop()
