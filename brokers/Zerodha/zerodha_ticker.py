import time
import json
import logging
import redis
from kiteconnect import KiteTicker

logging.basicConfig(level=logging.INFO)

class ZerodhaTicker:
    def __init__(self, api_key: str, access_token: str, user_id: str, redis_host="localhost", redis_port=6379):
        self.api_key = api_key
        self.access_token = f"{access_token}&user_id={user_id}"
        self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        self.kws = None
        self.is_connected = False

    def _init_ticker(self):
        self.kws = KiteTicker(self.api_key, self.access_token)

        self.kws.on_connect = self._on_connect
        self.kws.on_close = self._on_close
        self.kws.on_error = self._on_error
        self.kws.on_order_update = self._on_order_update
        self.kws.on_ticks = self._on_ticks

    def _on_connect(self, ws, response):
        logging.info(" WebSocket connected")
        self.is_connected = True

    def _on_close(self, ws, code, reason):
        logging.warning(f" WebSocket closed: {code} - {reason}")
        self.is_connected = False

        # Reconnect
        self._reconnect()

    def _on_error(self, ws, code, reason):
        logging.error(f" WebSocket error: {code} - {reason}")

    def _on_order_update(self, ws, order_data):
        logging.info(f" Order Update: {order_data}")

        payload = {
            "event": "ORDER_UPDATE",
            "order_id": order_data.get("order_id"),
            "status": order_data.get("status"),
            "details": order_data
        }

        self.redis.publish("zerodha.orders", json.dumps(payload))

    def _on_ticks(self, ws, ticks):
        logging.debug(f" Tick Update: {ticks}")

        payload = {
            "event": "TICK_UPDATE",
            "ticks": ticks
        }

        self.redis.publish("zerodha.ticks", json.dumps(payload))

    def _reconnect(self):
        logging.info(" Reconnecting WebSocket in 3 sec...")
        time.sleep(3)
        self.start()

    def start(self):
        logging.info("➡ Starting Zerodha WebSocket ticker...")
        self._init_ticker()

        # Threaded connect
        self.kws.connect(threaded=True)

        # Keep alive loop
        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                logging.info(" Stopping WebSocket ticker...")
                self.kws.stop()
                break

    def subscribe(self, instruments: list, mode="full"):
        """
        Subscribe to market data.
        arguments:
            - instruments: list of instrument_tokens [int, int, ...]
            - mode: 'full', 'quote', 'ltp'
        """
        if not self.is_connected:
            logging.error(" Not connected yet. Cannot subscribe.")
            return

        logging.info(f" Subscribing: {instruments} in {mode} mode")
        self.kws.subscribe(instruments)
        self.kws.set_mode(mode, instruments)

    def unsubscribe(self, instruments: list):
        if not self.is_connected:
            logging.error(" Not connected yet. Cannot unsubscribe.")
            return

        logging.info(f" Unsubscribing: {instruments}")
        self.kws.unsubscribe(instruments)
