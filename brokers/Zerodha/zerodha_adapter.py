import threading
import time
import logging
from api.auth import ZerodhaAuthAPI
from api.order import ZerodhaOrderAPI
from api.portfolio import ZerodhaPortfolioAPI
from utils.redis_publisher import RedisPublisher

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

class ZerodhaAdapter:

    TERMINAL_STATES = {'COMPLETE', 'CANCELLED', 'REJECTED'}

    def __init__(self, api_key, api_secret, redirect_url):
        self.api_key = api_key
        self.api_secret = api_secret
        self.redirect_url = redirect_url

        self.auth_api = ZerodhaAuthAPI(api_key, api_secret, redirect_url)
        self.order_api = None
        self.portfolio_api = None
        self.access_token = None

        self.redis_pub = RedisPublisher()

        self.monitored_orders = {}  
        self.stop_monitoring = False
        self.monitor_thread = None

        logging.info("ZERODHA ADAPTER INITIALIZED")
        logging.info("Login using this URL:")
        logging.info(self.auth_api.generate_login_url())

        try:
            token = input("Paste 'request_token' from browser here: ").strip()
            if token:
                self.login(token)
                logging.info("Login Successful")
        except Exception as e:
            logging.error(f"Login Failed: {e} !!")

    def get_login_url(self):
        return self.auth_api.generate_login_url()

    def login(self, request_token):
        logging.info(f"Logging in with token: {request_token[:6]}...")
        self.access_token = self.auth_api.exchange_token(request_token)

        self.order_api = ZerodhaOrderAPI(self.access_token, self.api_key)
        self.portfolio_api = ZerodhaPortfolioAPI(self.access_token, self.api_key)

        self.redis_pub.publish(
            "zerodha.auth",
            {
                "event": "LOGIN_SUCCESS",
                "access_token": self.access_token
            }
        )

        self._start_order_monitor()
        return {"access_token": self.access_token}

    def logout(self):
        self.stop_monitoring = True
        if self.monitor_thread:
            self.monitor_thread.join()
        
        self.access_token = None
        self.redis_pub.publish(
            "zerodha.auth",
            {"event": "LOGOUT"}
        )
        logging.info("Logged out successfully.")

    def _ensure_login(self):
        if not self.access_token or not self.order_api:
            raise RuntimeError(
                "User not logged in. Send LOGIN command first."
            )

    def _start_order_monitor(self):
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.stop_monitoring = False
            self.monitor_thread = threading.Thread(target=self._poll_orders, daemon=True)
            self.monitor_thread.start()
            logging.info("Background order monitor started.")

    def _poll_orders(self):
        while not self.stop_monitoring:
            if not self.monitored_orders:
                time.sleep(1)
                continue

            try:
                all_orders_response = self.order_api.get_orders()
                all_orders = all_orders_response.get('data', [])
                api_orders_map = {order['order_id']: order for order in all_orders}

                for order_id in list(self.monitored_orders):
                    if order_id in api_orders_map:
                        api_order_data = api_orders_map[order_id]
                        current_status = api_order_data.get('status')
                        local_data = self.monitored_orders[order_id]
                        last_known_status = local_data.get("last_status")

                        if current_status != last_known_status:
                            self._handle_status_change(order_id, last_known_status, current_status, api_order_data)
                            self.monitored_orders[order_id]["last_status"] = current_status

                        if current_status in self.TERMINAL_STATES:
                            logging.info(f"Order {order_id} reached terminal state: {current_status}. Removing from monitor.")
                            self.monitored_orders.pop(order_id, None)

            except Exception as e:
                logging.error(f"Error in monitoring thread: {e}")
            
            time.sleep(1)

    def _handle_status_change(self, order_id, old_status, new_status, order_data):
        logging.info(order_data)
        event_type = "ORDER_UPDATED"

        if new_status == "OPEN" and old_status == "INITIALIZED":
            event_type = "ORDER_ACCEPTED"
        elif new_status == "COMPLETE":
            event_type = "ORDER_TRADED"
        elif new_status == "CANCELLED":
            event_type = "ORDER_CANCELLED"
        elif new_status == "REJECTED":
            event_type = "ORDER_REJECTED"
        elif new_status == "UPDATE":
            event_type = "ORDER_MODIFIED"
        
        self.redis_pub.publish(
            "zerodha.orders",
            {
                "event": event_type,
                "order_id": order_id,
                "previous_status": old_status,
                "current_status": new_status,
                "details": order_data
            }
        )
        logging.info(f"Event Published: {event_type} for Order {order_id} ({old_status} -> {new_status})")

    def place_order(self, symbol, qty, order_type, transaction_type="BUY", product="MIS", exchange="NSE", price=0, trigger_price=0, validity="DAY"):
        self._ensure_login()
        response = self.order_api.place_order(symbol, qty, order_type, transaction_type, product, exchange, validity, price, trigger_price)

        try:
            order_id = response.get('data', {}).get('order_id')
            if order_id:
                self.monitored_orders[order_id] = {
                    "last_status": "INITIALIZED",
                    "symbol": symbol,
                    "qty": qty,
                    "transaction_type": transaction_type
                }
                logging.info(f"Order {order_id} ({symbol}) added to monitoring queue.")
        except Exception as e:
            logging.error(f"Could not extract order_id for monitoring: {e}")

        self.redis_pub.publish(
            "zerodha.orders",
            {
                "event": "ORDER_PLACED_REQ",
                "request": {
                    "symbol": symbol,
                    "qty": qty,
                    "order_type": order_type,
                    "transaction_type": transaction_type,
                },
                "response": response
            }
        )
        return response

    def modify_order(self, order_id, order_type, qty, validity):
        self._ensure_login()
        response = self.order_api.modify_order(order_id, order_type, qty, validity)

        if order_id in self.monitored_orders:
            logging.info(f"Order {order_id} modification request sent.")
        
        self.redis_pub.publish(
            "zerodha.orders",
            {
                "event": "ORDER_MODIFY_REQ",
                "order_id": order_id,
                "response": response
            }
        )
        return response

    def cancel_order(self, order_id):
        self._ensure_login()
        response = self.order_api.cancel_order(order_id)

        self.redis_pub.publish(
            "zerodha.orders",
            {
                "event": "ORDER_CANCEL_REQ",
                "order_id": order_id,
                "response": response
            }
        )
        return response

    def get_orders(self):
        self._ensure_login()
        response = self.order_api.get_orders()

        self.redis_pub.publish(
            "zerodha.orders",
            {
                "event": "ORDERS_FETCHED",
                "response": response
            }
        )
        return response

    def get_holdings(self):
        self._ensure_login()
        response = self.portfolio_api.get_holdings()

        self.redis_pub.publish(
            "zerodha.portfolio",
            {
                "event": "HOLDINGS_FETCHED",
                "response": response
            }
        )
        return response

    def get_positions(self):
        self._ensure_login()
        response = self.portfolio_api.get_positions()

        self.redis_pub.publish(
            "zerodha.portfolio",
            {
                "event": "POSITIONS_FETCHED",
                "response": response
            }
        )
        return response
