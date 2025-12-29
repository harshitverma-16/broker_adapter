import threading
import time
from api.auth import MotilalAuthAPI
from api.order import MotilalOrderAPI
from api.portfolio import MotilalPortfolioAPI
from brokers.utils.redis_publisher import RedisPublisher


class MotilalOswalAdapter:

    # Terminal states – stop monitoring once reached
    TERMINAL_STATES = {"COMPLETE", "CANCELLED", "REJECTED"}

    def __init__(self, api_key, client_id, password, dob):
        self.api_key = api_key
        self.client_id = client_id
        self.password = password
        self.dob = dob

        self.auth_api = MotilalAuthAPI(api_key, client_id, password, dob)
        self.order_api = None
        self.portfolio_api = None
        self.access_token = None

        # Redis
        self.redis_pub = RedisPublisher()

        # Order Monitoring
        self.monitored_orders = {}
        self.stop_monitoring = False
        self.monitor_thread = None

        print("MOTILAL OSWAL ADAPTER INITIALIZED")

        try:
            self.login()
            print("Login Successful")
        except Exception as e:
            print(f"Login Failed: {e}")

    # ------------------ Authentication ------------------

    def login(self):
        self.access_token = self.auth_api.login()

        self.order_api = MotilalOrderAPI(self.access_token)
        self.portfolio_api = MotilalPortfolioAPI(self.access_token)

        self.redis_pub.publish(
            "motilal.auth",
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
            "motilal.auth",
            {"event": "LOGOUT"}
        )
        print("Logged out successfully")

    def _ensure_login(self):
        if not self.access_token or not self.order_api:
            raise RuntimeError("User not logged in")

    # ------------------ Monitoring ------------------

    def _start_order_monitor(self):
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.stop_monitoring = False
            self.monitor_thread = threading.Thread(
                target=self._poll_orders,
                daemon=True
            )
            self.monitor_thread.start()
            print("Background order monitor started")

    def _poll_orders(self):
        while not self.stop_monitoring:
            if not self.monitored_orders:
                time.sleep(1)
                continue

            try:
                response = self.order_api.get_orders()
                all_orders = response.get("data", [])

                api_orders_map = {
                    order["order_id"]: order for order in all_orders
                }

                for order_id in list(self.monitored_orders.keys()):
                    if order_id not in api_orders_map:
                        continue

                    api_order = api_orders_map[order_id]
                    current_status = api_order.get("status")
                    local_data = self.monitored_orders[order_id]
                    last_status = local_data.get("last_status")

                    if current_status != last_status:
                        self._handle_status_change(
                            order_id,
                            last_status,
                            current_status,
                            api_order
                        )
                        self.monitored_orders[order_id]["last_status"] = current_status

                    if current_status in self.TERMINAL_STATES:
                        print(
                            f"Order {order_id} reached terminal state: {current_status}"
                        )
                        self.monitored_orders.pop(order_id, None)

            except Exception as e:
                print(f"Monitoring error: {e}")

            time.sleep(1)

    def _handle_status_change(self, order_id, old_status, new_status, order_data):
        event_type = "ORDER_UPDATED"

        if new_status == "OPEN" and old_status == "INITIALIZED":
            event_type = "ORDER_ACCEPTED"
        elif new_status == "COMPLETE":
            event_type = "ORDER_TRADED"
        elif new_status == "CANCELLED":
            event_type = "ORDER_CANCELLED"
        elif new_status == "REJECTED":
            event_type = "ORDER_REJECTED"

        self.redis_pub.publish(
            "motilal.orders",
            {
                "event": event_type,
                "order_id": order_id,
                "previous_status": old_status,
                "current_status": new_status,
                "details": order_data
            }
        )

        print(
            f"Event Published: {event_type} "
            f"({old_status} → {new_status}) Order {order_id}"
        )

    # ------------------ Orders API ------------------

    def place_order(
        self,
        symbol,
        qty,
        order_type,
        transaction_type="BUY",
        product="MIS",
        exchange="NSE",
        price=0,
        trigger_price=0,
        validity="DAY"
    ):
        self._ensure_login()

        response = self.order_api.place_order(
            symbol=symbol,
            qty=qty,
            order_type=order_type,
            transaction_type=transaction_type,
            product=product,
            exchange=exchange,
            price=price,
            trigger_price=trigger_price,
            validity=validity
        )

        order_id = response.get("data", {}).get("order_id")

        if order_id:
            self.monitored_orders[order_id] = {
                "last_status": "INITIALIZED",
                "symbol": symbol,
                "qty": qty,
                "transaction_type": transaction_type
            }

        self.redis_pub.publish(
            "motilal.orders",
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

    def modify_order(self, order_id, qty, price=0, trigger_price=0):
        self._ensure_login()
        response = self.order_api.modify_order(
            order_id, qty, price, trigger_price
        )

        self.redis_pub.publish(
            "motilal.orders",
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
            "motilal.orders",
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
            "motilal.orders",
            {
                "event": "ORDERS_FETCHED",
                "response": response
            }
        )
        return response

    # ------------------ Portfolio API ------------------

    def get_holdings(self):
        self._ensure_login()
        response = self.portfolio_api.get_holdings()

        self.redis_pub.publish(
            "motilal.portfolio",
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
            "motilal.portfolio",
            {
                "event": "POSITIONS_FETCHED",
                "response": response
            }
        )
        return response
