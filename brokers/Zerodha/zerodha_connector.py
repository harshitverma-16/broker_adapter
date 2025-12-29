import json
import redis
import threading
import logging
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from brokers.Zerodha.utils.broker_order_mapper import BrokerOrderMapper
from zerodha_adapter import ZerodhaAdapter

# --- Configuration ---
REDIS_HOST = "localhost"
REDIS_PORT = 6379
CH_REQUESTS = "adapter.channel"   # Incoming commands from Blitz
CH_RESPONSES = "blitz.responses" # Outgoing responses to Blitz

# Zerodha Credentials
API_KEY = "e2zjycwhnc7xknxp"
API_SECRET = "jvo244jvuzepmzhkhiucs4pd6hpmdpc4"
REDIRECT_URL = "http://localhost" 

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

class ZerodhaConnector:
    def _forward_adapter_events(self):
        """Listen to adapter channels and forward all events to blitz.responses"""
        pubsub = self.adapter.redis_pub.redis.pubsub()
        pubsub.subscribe("zerodha.orders", "zerodha.auth", "zerodha.portfolio")

        logging.info("[Connector] Listening to adapter channels...")

        for msg in pubsub.listen():
            if msg["type"] != "message":
                continue

            try:
                raw_data = msg["data"]
                channel = msg["channel"]

                logging.info(f"[Adapter Event] {channel} -> {raw_data}")

                # Only map ORDER events
                if channel == "zerodha.orders":
                    try:
                        data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data

                        if data.get("event") == "ORDERS_FETCHED":
                            orders_list = data["response"]["data"]
                            logging.info(f"[ORDERS_FETCHED] {len(orders_list)} orders received")

                            for order in orders_list:
                                logging.info(f"Mapping order_id={order.get('order_id')}")

                                # Wrap order in dict format, not string
                                wrapped_order = {
                                    "details": order,
                                    "order_id": order.get("order_id")
                                }

                                # Pass dict directly, do not dump to string
                                order_log = BrokerOrderMapper.map("zerodha", wrapped_order)
                                logging.info(f"[OrderLog] {order_log} orders received")
                                # Publish as JSON to Redis
                                self.redis.publish("blitz.responses", order_log.to_json())
                                logging.info(f"[Blitz OrderLog Published] ExchangeOrderId={order_log.ExchangeOrderId}")

                    except Exception as e:
                        logging.error(f"[Order Mapping Error] {e}")

                else:
                    # auth / portfolio can still be forwarded as-is
                    self.redis.publish("blitz.responses", raw_data)

            except Exception as e:
                logging.error(f"[Forward Adapter Error] {e}")

    def __init__(self):
        logging.info("[Connector] Initializing Adapter (Offline Mode)...")
        
        self.adapter = ZerodhaAdapter(API_KEY, API_SECRET, REDIRECT_URL)
        
        logging.info("[Connector] Connecting to Redis...")
        self.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        self.is_running = False
        threading.Thread(target=self._forward_adapter_events, daemon=True).start()

        if self.adapter.access_token:
            logging.info("'LOGIN_SUCCESS' to Blitz...")
            self.redis.publish(CH_RESPONSES, json.dumps({
                "request_id": "STARTUP",
                "status": "LOGIN_SUCCESS",
                "data": {"message": "Authenticated"}
            }))

    def start(self):
        self.pubsub.subscribe(CH_REQUESTS)
        self.is_running = True
        logging.info(f"[Connector] Online and listening on '{CH_REQUESTS}'...")

        for message in self.pubsub.listen():
            if not self.is_running:
                break
            if message["type"] == "message":
                threading.Thread(target=self._process_message, args=(message["data"],)).start()

    def stop(self):
        self.is_running = False
        self.pubsub.unsubscribe()
        self.adapter.logout()
        logging.info("[Connector] Stopped.")
    

    def _process_message(self, raw_data):
        try:
            payload = json.loads(raw_data)
            req_id = payload.get("request_id")
            action = payload.get("action")
            blitz_data = payload.get("data", {})

            logging.info(f" -> Received: {action} [ID: {req_id}]")
            
            result = None
            status = "SUCCESS"
            error_msg = None

            try:
                if action == "GET_LOGIN_URL":
                    url = self.adapter.get_login_url()
                    result = {"login_url": url}

                elif action == "LOGIN":
                    req_token = blitz_data.get("request_token")
                    if not req_token:
                        raise ValueError("Missing 'request_token'")
                    result = self.adapter.login(req_token)

                elif action == "LOGOUT":
                    self.adapter.logout()
                    result = {"message": "Logged out successfully"}

                elif action == "PLACE_ORDER":
                    params = self._map_blitz_to_zerodha(blitz_data)
                    logging.info(f"Mapped Zerodha payload: {params}")
                    result = self.adapter.place_order(
                        symbol=params["symbol"],
                        qty=params["qty"],
                        order_type=params["order_type"],
                        transaction_type=params["transaction_type"],
                        product=params["product"],
                        exchange=params["exchange"],
                        price=params["price"],
                        trigger_price=params["trigger_price"],
                        validity=params["validity"]
                    )

                elif action == "MODIFY_ORDER":
                    result = self.adapter.modify_order(
                        order_id=blitz_data.get("order_id"),
                        order_type=blitz_data.get("orderType", "LIMIT"),
                        qty=int(blitz_data.get("quantity", 0)),
                        validity=blitz_data.get("validity", "DAY")
                    )

                elif action == "CANCEL_ORDER":
                    result = self.adapter.cancel_order(blitz_data.get("order_id"))

                elif action == "GET_ORDERS":
                    result = self.adapter.get_orders()

                elif action == "GET_HOLDINGS":
                    result = self.adapter.get_holdings()

                elif action == "GET_POSITIONS":
                    result = self.adapter.get_positions()

                else:
                    raise ValueError(f"Unknown Action: {action}")

            except Exception as e:
                logging.error(f" !! Error executing {action}: {e}")
                status = "ERROR"
                error_msg = str(e)

            self._send_response(req_id, status, result, error_msg)

        except json.JSONDecodeError:
            logging.critical(" !! Critical: Failed to decode JSON message from Redis")

    def _map_blitz_to_zerodha(self, data):
        raw_symbol = data.get("symbol", "")
        
        if "|" in raw_symbol:
            exchange, tradingsymbol = raw_symbol.split("|", 1)
        else:
            exchange = "NSE"
            tradingsymbol = raw_symbol

        tif = data.get("tif", "DAY")
        validity = "IOC" if tif == "IOC" else "DAY"
        product = data.get("product", "MIS")
        
        payload = {
            "exchange": exchange,
            "symbol": tradingsymbol,
            "qty": int(data.get("quantity")),
            "order_type": data.get("orderType"),
            "transaction_type": data.get("orderSide"),
            "product": product,
            "price": float(data.get("price")),
            "trigger_price": float(data.get("stopPrice")),
            "validity": validity
        }
        return payload
    
    def _send_response(self, req_id, status, data=None, error=None):
        response_payload = {
            "request_id": req_id,
            "status": status,
            "data": data,
            "error": error
        }
        json_dump = json.dumps(response_payload)
        self.redis.publish(CH_RESPONSES, json_dump)
        logging.info(f"Response from Zerodha [{json_dump}]")
        logging.info(f" <- Sent {status} for [ID: {req_id}]")

if __name__ == "__main__":
    connector = ZerodhaConnector()
    try:
        connector.start()
    except KeyboardInterrupt:
        connector.stop()
