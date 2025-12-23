import json
import redis
import threading

from zerodha_adapter import ZerodhaAdapter

# --- Configuration ---
REDIS_HOST = "localhost"
REDIS_PORT = 6379
CH_REQUESTS = "blitz.requests"   # Incoming commands from Blitz
CH_RESPONSES = "blitz.responses" # Outgoing responses to Blitz

# Zerodha Credentials

API_KEY = "2i4ayyawcrptt24h"
API_SECRET = "2lxel09zt42jim5veokpgg6slrih2fpa"
REDIRECT_URL = "http://localhost" 

class ZerodhaConnector:
    def __init__(self):
        print("[Connector] Initializing Adapter (Offline Mode)...")
        
        # Initialize Adapter
        self.adapter = ZerodhaAdapter(API_KEY, API_SECRET, REDIRECT_URL)
        
        # Initialize Redis
        print("[Connector] Connecting to Redis...")
        self.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        self.is_running = False

        if self.adapter.access_token:
            print("'LOGIN_SUCCESS' to Blitz...")
            self.redis.publish(CH_RESPONSES, json.dumps({
                "request_id": "STARTUP",
                "status": "LOGIN_SUCCESS",
                "data": {"message": "Authenticated"}
            }))

    def start(self):
        """Starts the main listener loop."""
        self.pubsub.subscribe(CH_REQUESTS)
        self.is_running = True
        print(f"[Connector] Online and listening on '{CH_REQUESTS}'...")

        # Blocking listener loop
        for message in self.pubsub.listen():
            if not self.is_running:
                break
            
            if message["type"] == "message":
                # Process in a separate thread to prevent blocking the listener
                threading.Thread(target=self._process_message, args=(message["data"],)).start()

    def stop(self):
        """Stops the connector safely."""
        self.is_running = False
        self.pubsub.unsubscribe()
        self.adapter.logout()
        print("[Connector] Stopped.")

    def _process_message(self, raw_data):
        """Decodes JSON, routes the command, and sends the response."""
        try:
            payload = json.loads(raw_data)
            
            # Standard Envelope: { "request_id": "...", "action": "...", "data": ... }
            req_id = payload.get("request_id")
            action = payload.get("action")
            blitz_data = payload.get("data", {})

            print(f" -> Received: {action} [ID: {req_id}]")
            
            result = None
            status = "SUCCESS"
            error_msg = None

            try:
                
                # AUTHENTICATION COMMANDS
                
                if action == "GET_LOGIN_URL":
                    # Step 1: Blitz asks for URL
                    url = self.adapter.get_login_url()
                    result = {"login_url": url}

                elif action == "LOGIN":
                    # Step 2: Blitz sends the token user got from browser
                    req_token = blitz_data.get("request_token")
                    if not req_token:
                        raise ValueError("Missing 'request_token'")
                    result = self.adapter.login(req_token)

                elif action == "LOGOUT":
                    self.adapter.logout()
                    result = {"message": "Logged out successfully"}

                
                # ORDER COMMANDS
                
                elif action == "PLACE_ORDER":
                    # Convert Blitz payload to Zerodha format
                    params = self._map_blitz_to_zerodha(blitz_data)
                    
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
                    # Note: Blitz modify payload might differ, assuming standard keys here
                    result = self.adapter.modify_order(
                        order_id=blitz_data.get("order_id"),
                        order_type=blitz_data.get("orderType", "LIMIT"),
                        qty=int(blitz_data.get("quantity", 0)),
                        validity=blitz_data.get("validity", "DAY")
                    )

                elif action == "CANCEL_ORDER":
                    result = self.adapter.cancel_order(blitz_data.get("order_id"))

                
                # DATA COMMANDS
                
                elif action == "GET_ORDERS":
                    result = self.adapter.get_orders()

                elif action == "GET_HOLDINGS":
                    result = self.adapter.get_holdings()

                elif action == "GET_POSITIONS":
                    result = self.adapter.get_positions()

                else:
                    raise ValueError(f"Unknown Action: {action}")

            except Exception as e:
                print(f" !! Error executing {action}: {e}")
                # traceback.print_exc() # Uncomment for debugging
                status = "ERROR"
                error_msg = str(e)

            # Send Final Response
            self._send_response(req_id, status, result, error_msg)

        except json.JSONDecodeError:
            print(" !! Critical: Failed to decode JSON message from Redis")

    def _map_blitz_to_zerodha(self, data):
        """
        Maps Blitz generic keys to Zerodha specific keys.
        Handles Equity (NSE|RELIANCE) and F&O (NSEFO|...) symbols.
        """
        
        # 1. Parse Symbol & Exchange
        raw_symbol = data.get("symbol", "")
        
        if "|" in raw_symbol:
            # Explicit format: "NSE|RELIANCE" or "NSEFO|NIFTY..."
            exchange, tradingsymbol = raw_symbol.split("|", 1)
        else:
            # Implicit format: "RELIANCE" -> Default to NSE Equity
            exchange = "NSE"
            tradingsymbol = raw_symbol

        # 2. Map Time In Force (Validity)
        # Blitz: "GTD", "IOC", "DAY" -> Zerodha: "IOC", "DAY"
        tif = data.get("tif", "DAY") # Default to DAY
        validity = "IOC" if tif == "IOC" else "DAY"

        # 3. Map Product
        product = data.get("product", "MIS") # Default to Intraday

        return {
            "exchange": exchange,
            "symbol": tradingsymbol,
            "qty": int(data.get("quantity")),
            "order_type": data.get("orderType"),    # LIMIT, MARKET, SL, SL-M
            "transaction_type": data.get("orderSide"),# BUY / SELL
            "product": product,
            "price": float(data.get("price")),            # Required for LIMIT
            "trigger_price": float(data.get("stopPrice")),# Mapped from stopPrice
            "validity": validity
        }

    def _send_response(self, req_id, status, data=None, error=None):
        """Publishes the processed result back to Blitz."""
        response_payload = {
            "request_id": req_id,
            "status": status,
            "data": data,
            "error": error
        }
        
        self.redis.publish(CH_RESPONSES, json.dumps(response_payload))
        print(f" <- Sent {status} for [ID: {req_id}]")


if __name__ == "__main__":
    connector = ZerodhaConnector()
    try:
        connector.start()
    except KeyboardInterrupt:
        connector.stop()