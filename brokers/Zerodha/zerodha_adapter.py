
import threading
import time
from api.auth import ZerodhaAuthAPI
from api.order import ZerodhaOrderAPI
from api.portfolio import ZerodhaPortfolioAPI
from utils.redis_publisher import RedisPublisher


class ZerodhaAdapter:

    # Define Terminal States (Orders stop being monitored when they reach these)
    TERMINAL_STATES = {'COMPLETE', 'CANCELLED', 'REJECTED'}

    def __init__(self, api_key, api_secret, redirect_url):
        self.api_key = api_key
        self.api_secret = api_secret
        self.redirect_url = redirect_url

        self.auth_api = ZerodhaAuthAPI(api_key, api_secret, redirect_url)
        self.order_api = None
        self.portfolio_api = None
        self.access_token = None

        # Redis publisher
        self.redis_pub = RedisPublisher()

        # Monitoring State
        self.monitored_orders = {}  
        self.stop_monitoring = False
        self.monitor_thread = None

        print("ZERODHA ADAPTER INITIALIZED")
        print("Status: Offline (Waiting for LOGIN command via Redis)")

    def get_login_url(self):
        """Exposes the login URL generation from the Auth API."""
        return self.auth_api.generate_login_url()

    # Authentication
    def login(self, request_token):
        print(f"Logging in with token: {request_token[:6]}...")
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

        # Start the monitoring thread after successful login
        self._start_order_monitor()

        # Return token so Connector can send success response
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
        print("Logged out successfully.")

    def _ensure_login(self):
        if not self.access_token or not self.order_api:
            raise RuntimeError(
                "User not logged in. Send LOGIN command first."
            )

    # ------------------ Monitoring ------------------

    def _start_order_monitor(self):
        """Starts a background thread to poll order status."""
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.stop_monitoring = False
            self.monitor_thread = threading.Thread(target=self._poll_orders, daemon=True)
            self.monitor_thread.start()
            print("Background order monitor started.")

    def _poll_orders(self):
        """Polls Zerodha every second to check status of monitored orders."""
        while not self.stop_monitoring:
            if not self.monitored_orders:
                time.sleep(1)
                continue

            try:
                # 1. Fetch all orders from Zerodha
                all_orders_response = self.order_api.get_orders()
                all_orders = all_orders_response.get('data', [])

                # 2. Create map for quick lookup: {order_id: order_data_from_api}
                api_orders_map = {order['order_id']: order for order in all_orders}

                # 3. Iterate over our local "Open Order List"
                for order_id in list(self.monitored_orders):
                    
                    if order_id in api_orders_map:
                        api_order_data = api_orders_map[order_id]
                        current_status = api_order_data.get('status') # e.g., OPEN, COMPLETE, CANCELLED
                        
                        # Get local tracked data
                        local_data = self.monitored_orders[order_id]
                        last_known_status = local_data.get("last_status")

                        # 4. Check for State Change
                        if current_status != last_known_status:
                            self._handle_status_change(order_id, last_known_status, current_status, api_order_data)
                            
                            # Update local status
                            self.monitored_orders[order_id]["last_status"] = current_status

                        # 5. Check if Terminal State (Remove from list)
                        if current_status in self.TERMINAL_STATES:
                            print(f"Order {order_id} reached terminal state: {current_status}. Removing from monitor.")
                            self.monitored_orders.pop(order_id, None)

            except Exception as e:
                print(f"Error in monitoring thread: {e}")
            
            time.sleep(1)

    def _handle_status_change(self, order_id, old_status, new_status, order_data):
        """Determines the event type based on status change and publishes to Redis."""
        event_type = "ORDER_UPDATED" # Default

        # Logic to determine specific event names based on status
        if new_status == "OPEN" and old_status == "INITIALIZED":
            event_type = "ORDER_ACCEPTED"
        elif new_status == "COMPLETE":
            event_type = "ORDER_TRADED"
        elif new_status == "CANCELLED":
            event_type = "ORDER_CANCELLED"
        elif new_status == "REJECTED":
            event_type = "ORDER_REJECTED"
        elif new_status == "UPDATE": # Hypothetical status for modification
            event_type = "ORDER_MODIFIED"
        
        # Publish to Redis
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
        print(f"Event Published: {event_type} for Order {order_id} ({old_status} -> {new_status})")


    # ------------------ Orders API ------------------

    def place_order(self, symbol, qty, order_type, transaction_type="BUY", product="MIS", exchange="NSE", price=0, trigger_price=0, validity="DAY"):
        self._ensure_login()
    
        # Updated to pass price and trigger_price to the API
        response = self.order_api.place_order(
            symbol, qty, order_type, transaction_type, product, exchange, validity, price, trigger_price
        )

        try:
            order_id = response.get('data', {}).get('order_id')
            if order_id:
                # Insert into Open Order List
                self.monitored_orders[order_id] = {
                    "last_status": "INITIALIZED",
                    "symbol": symbol,
                    "qty": qty,
                    "transaction_type": transaction_type
                }
                print(f"Order {order_id} ({symbol}) added to monitoring queue.")
        except Exception as e:
            print(f"Could not extract order_id for monitoring: {e}")

        # Immediate acknowledgement of the request
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
            print(f"Order {order_id} modification request sent.")
        
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

    # Portfolio API
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




# import threading
# import time
# from api.auth import ZerodhaAuthAPI
# from api.order import ZerodhaOrderAPI
# from api.portfolio import ZerodhaPortfolioAPI
# from utils.redis_publisher import RedisPublisher


# class ZerodhaAdapter:

#     # Define Terminal States (Orders stop being monitored when they reach these)
#     TERMINAL_STATES = {'COMPLETE', 'CANCELLED', 'REJECTED'}

#     def __init__(self, api_key, api_secret, redirect_url):
#         self.api_key = api_key
#         self.api_secret = api_secret
#         self.redirect_url = redirect_url

#         self.auth_api = ZerodhaAuthAPI(api_key, api_secret, redirect_url)
#         self.order_api = None
#         self.portfolio_api = None
#         self.access_token = None

#         # Redis publisher
#         self.redis_pub = RedisPublisher()

#         # Monitoring State
#         self.monitored_orders = {}  
#         self.stop_monitoring = False
#         self.monitor_thread = None

#         print("ZERODHA ADAPTER INITIALIZED")
#         print("Please login using this URL:")
#         print(self.auth_api.generate_login_url())

#         try:
#             token = input("Paste 'request_token' from browser here: ").strip()
#             if token:
#                 self.login(token)
#                 print("!! Login Successful during initialization !!")
#         except Exception as e:
#             print(f"!! Login Failed during initialization: {e} !!")

#     def get_login_url(self):
#         """Exposes the login URL generation from the Auth API."""
#         return self.auth_api.generate_login_url()

#     # Authentication
#     def login(self, request_token):
#         self.access_token = self.auth_api.exchange_token(request_token)

#         self.order_api = ZerodhaOrderAPI(self.access_token, self.api_key)
#         self.portfolio_api = ZerodhaPortfolioAPI(self.access_token, self.api_key)

#         self.redis_pub.publish(
#             "zerodha.auth",
#             {
#                 "event": "LOGIN_SUCCESS",
#                 "access_token": self.access_token
#             }
#         )

#         # Start the monitoring thread after successful login
#         self._start_order_monitor()

#         return self.access_token

#     def logout(self):
#         self.stop_monitoring = True
#         if self.monitor_thread:
#             self.monitor_thread.join()
        
#         self.access_token = None
#         self.redis_pub.publish(
#             "zerodha.auth",
#             {"event": "LOGOUT"}
#         )

#     def _ensure_login(self):
#         if not self.access_token or not self.order_api:
#             raise RuntimeError(
#                 "User not logged in. Call login(request_token) first."
#             )

#     # ------------------ Monitoring ------------------

#     def _start_order_monitor(self):
#         """Starts a background thread to poll order status."""
#         if self.monitor_thread is None or not self.monitor_thread.is_alive():
#             self.stop_monitoring = False
#             self.monitor_thread = threading.Thread(target=self._poll_orders, daemon=True)
#             self.monitor_thread.start()
#             print("Background order monitor started.")

#     def _poll_orders(self):
#         """Polls Zerodha every second to check status of monitored orders."""
#         while not self.stop_monitoring:
#             if not self.monitored_orders:
#                 time.sleep(1)
#                 continue

#             try:
#                 # 1. Fetch all orders from Zerodha
#                 all_orders_response = self.order_api.get_orders()
#                 all_orders = all_orders_response.get('data', [])

#                 # 2. Create map for quick lookup: {order_id: order_data_from_api}
#                 api_orders_map = {order['order_id']: order for order in all_orders}

#                 # 3. Iterate over our local "Open Order List"
#                 for order_id in list(self.monitored_orders):
                    
#                     if order_id in api_orders_map:
#                         api_order_data = api_orders_map[order_id]
#                         current_status = api_order_data.get('status') # e.g., OPEN, COMPLETE, CANCELLED
                        
#                         # Get local tracked data
#                         local_data = self.monitored_orders[order_id]
#                         last_known_status = local_data.get("last_status")

#                         # 4. Check for State Change
#                         if current_status != last_known_status:
#                             self._handle_status_change(order_id, last_known_status, current_status, api_order_data)
                            
#                             # Update local status
#                             self.monitored_orders[order_id]["last_status"] = current_status

#                         # 5. Check if Terminal State (Remove from list)
#                         if current_status in self.TERMINAL_STATES:
#                             print(f"Order {order_id} reached terminal state: {current_status}. Removing from monitor.")
#                             self.monitored_orders.pop(order_id, None)

#             except Exception as e:
#                 print(f"Error in monitoring thread: {e}")
            
#             time.sleep(1)

#     def _handle_status_change(self, order_id, old_status, new_status, order_data):
#         """Determines the event type based on status change and publishes to Redis."""
#         event_type = "ORDER_UPDATED" # Default

#         # Logic to determine specific event names based on status
#         if new_status == "OPEN" and old_status == "INITIALIZED":
#             event_type = "ORDER_ACCEPTED"
#         elif new_status == "COMPLETE":
#             event_type = "ORDER_TRADED"
#         elif new_status == "CANCELLED":
#             event_type = "ORDER_CANCELLED"
#         elif new_status == "REJECTED":
#             event_type = "ORDER_REJECTED"
#         elif new_status == "UPDATE": # Hypothetical status for modification
#             event_type = "ORDER_MODIFIED"
        
#         # Publish to Redis
#         self.redis_pub.publish(
#             "zerodha.orders",
#             {
#                 "event": event_type,
#                 "order_id": order_id,
#                 "previous_status": old_status,
#                 "current_status": new_status,
#                 "details": order_data
#             }
#         )
#         print(f"Event Published: {event_type} for Order {order_id} ({old_status} -> {new_status})")


#     # ------------------ Orders API ------------------

#     def place_order(self, symbol, qty, order_type, transaction_type="BUY", product="MIS", exchange="NSE"):
#         self._ensure_login()
    
#         response = self.order_api.place_order(
#             symbol, qty, order_type, transaction_type, product, exchange
#         )

#         try:
#             order_id = response.get('data', {}).get('order_id')
#             if order_id:
#                 # Insert into Open Order List
#                 # We start with 'INITIALIZED' so that when API returns 'OPEN', 
#                 # the poller detects a change and fires 'ORDER_ACCEPTED'
#                 self.monitored_orders[order_id] = {
#                     "last_status": "INITIALIZED",
#                     "symbol": symbol,
#                     "qty": qty,
#                     "transaction_type": transaction_type
#                 }
#                 print(f"Order {order_id} ({symbol}) added to monitoring queue.")
#         except Exception as e:
#             print(f"Could not extract order_id for monitoring: {e}")

#         # Immediate acknowledgement of the request
#         self.redis_pub.publish(
#             "zerodha.orders",
#             {
#                 "event": "ORDER_PLACED_REQ",
#                 "request": {
#                     "symbol": symbol,
#                     "qty": qty,
#                     "order_type": order_type,
#                     "transaction_type": transaction_type,
#                 },
#                 "response": response
#             }
#         )
#         return response

#     def modify_order(self, order_id, order_type, qty, validity):
#         self._ensure_login()
#         response = self.order_api.modify_order(order_id, order_type, qty, validity)

#         # If we modify an order, ensure it is still in our monitoring list
#         # If it was previously removed (unlikely if active), we add it back
#         if order_id in self.monitored_orders:
#             # We don't change status here, we let the poller detect the update
#             print(f"Order {order_id} modification request sent.")
        
#         self.redis_pub.publish(
#             "zerodha.orders",
#             {
#                 "event": "ORDER_MODIFY_REQ",
#                 "order_id": order_id,
#                 "response": response
#             }
#         )
#         return response

#     def cancel_order(self, order_id):
#         self._ensure_login()
#         response = self.order_api.cancel_order(order_id)

#         self.redis_pub.publish(
#             "zerodha.orders",
#             {
#                 "event": "ORDER_CANCEL_REQ",
#                 "order_id": order_id,
#                 "response": response
#             }
#         )
#         return response

#     def get_orders(self):
#         self._ensure_login()
#         response = self.order_api.get_orders()

#         self.redis_pub.publish(
#             "zerodha.orders",
#             {
#                 "event": "ORDERS_FETCHED",
#                 "response": response
#             }
#         )
#         return response

#     # Portfolio API
#     def get_holdings(self):
#         self._ensure_login()
#         response = self.portfolio_api.get_holdings()

#         self.redis_pub.publish(
#             "zerodha.portfolio",
#             {
#                 "event": "HOLDINGS_FETCHED",
#                 "response": response
#             }
#         )
#         return response

#     def get_positions(self):
#         self._ensure_login()
#         response = self.portfolio_api.get_positions()

#         self.redis_pub.publish(
#             "zerodha.portfolio",
#             {
#                 "event": "POSITIONS_FETCHED",
#                 "response": response
#             }
#         )
#         return response


# # from urllib import response
# # #from base.base_adapter import BaseAdapter
# # from api.auth import ZerodhaAuthAPI
# # from api.order import ZerodhaOrderAPI
# # from api.portfolio import ZerodhaPortfolioAPI
# # from utils.redis_publisher import RedisPublisher


# # class ZerodhaAdapter:

# #     def __init__(self, api_key, api_secret, redirect_url):
# #         self.api_key = api_key
# #         self.api_secret = api_secret
# #         self.redirect_url = redirect_url

# #         self.auth_api = ZerodhaAuthAPI(api_key, api_secret, redirect_url)
# #         self.order_api = None
# #         self.portfolio_api = None
# #         self.access_token = None

# #         # Redis publisher
# #         self.redis_pub = RedisPublisher()


# #         print("ZERODHA ADAPTER INITIALIZED")
# #         print("Please login using this URL:")
# #         print(self.auth_api.generate_login_url())

# #         try:
# #             token = input("Paste 'request_token' from browser here: ").strip()
# #             if token:
# #                 self.login(token)
# #                 print("!! Login Successful during initialization !!")
# #         except Exception as e:
# #             print(f"!! Login Failed during initialization: {e} !!")

# #     def get_login_url(self):
# #         """Exposes the login URL generation from the Auth API."""
# #         return self.auth_api.generate_login_url()

# #     # Authentication
# #     def login(self, request_token):
# #         self.access_token = self.auth_api.exchange_token(request_token)

# #         self.order_api = ZerodhaOrderAPI(self.access_token, self.api_key)
# #         self.portfolio_api = ZerodhaPortfolioAPI(self.access_token, self.api_key)

# #         self.redis_pub.publish(
# #             "zerodha.auth",
# #             {
# #                 "event": "LOGIN_SUCCESS",
# #                 "access_token": self.access_token
# #             }
# #         )

# #         return self.access_token

# #     def logout(self):
# #         self.access_token = None
# #         self.redis_pub.publish(
# #             "zerodha.auth",
# #             {"event": "LOGOUT"}
# #         )

# #     def _ensure_login(self):
# #         if not self.access_token or not self.order_api:
# #             raise RuntimeError(
# #                 "User not logged in. Call login(request_token) first."
# #             )

# #     # Orders API

# #     def place_order(self, symbol, qty, order_type, transaction_type="BUY", product="MIS", exchange="NSE"):
# #         self._ensure_login()
    
    
# #         response = self.order_api.place_order(
# #             symbol, 
# #             qty, 
# #             order_type, 
# #             transaction_type, 
# #             product, 
# #             exchange
# #         )

# #         self.redis_pub.publish(
# #             "zerodha.orders",
# #             {
# #                 "event": "ORDER_PLACED",
# #                 "request": {
# #                     "symbol": symbol,
# #                     "qty": qty,
# #                     "order_type": order_type,
# #                     "transaction_type": transaction_type,
# #                     "product": product,                    
# #                 },
# #                 "response": response
# #             }
# #         )
# #         return response

# #     def modify_order(self, order_id, order_type, qty, validity):
# #         self._ensure_login()
# #         response = self.order_api.modify_order(order_id, order_type, qty, validity)

# #         self.redis_pub.publish(
# #             "zerodha.orders",
# #             {
# #                 "event": "ORDER_MODIFIED",
# #                 "order_id": order_id,
# #                 "response": response
# #             }
# #         )
# #         return response

# #     def cancel_order(self, order_id):
# #         self._ensure_login()
# #         response = self.order_api.cancel_order(order_id)

# #         self.redis_pub.publish(
# #             "zerodha.orders",
# #             {
# #                 "event": "ORDER_CANCELLED",
# #                 "order_id": order_id,
# #                 "response": response
# #             }
# #         )
# #         return response

# #     def get_orders(self):
# #         self._ensure_login()
# #         response = self.order_api.get_orders()

# #         self.redis_pub.publish(
# #             "zerodha.orders",
# #             {
# #                 "event": "ORDERS_FETCHED",
# #                 "response": response
# #             }
# #         )
# #         return response

# #     # Portfolio API
# #     def get_holdings(self):
# #         self._ensure_login()
# #         response = self.portfolio_api.get_holdings()

# #         self.redis_pub.publish(
# #             "zerodha.portfolio",
# #             {
# #                 "event": "HOLDINGS_FETCHED",
# #                 "response": response
# #             }
# #         )
# #         return response

# #     def get_positions(self):
# #         self._ensure_login()
# #         response = self.portfolio_api.get_positions()

# #         self.redis_pub.publish(
# #             "zerodha.portfolio",
# #             {
# #                 "event": "POSITIONS_FETCHED",
# #                 "response": response
# #             }
# #         )
# #         return response



# # # -----------------------Testing----------------------

# # #client = ZerodhaAdapter("2i4ayyawcrptt24h", "2lxel09zt42jim5veokpgg6slrih2fpa", "http://localhost")

# # #client.logout()
# # #print("Logged out successfully.")

# # # login_url = client.get_login_url()
# # # print(f"Open this URL in browser:\n{login_url}")

# # # req_token = input("Enter the request token from URL: ").strip()
# # # access_token = client.login(req_token)
# # # print(f"Access Token: {access_token}") 

# # # print("logout now")
# # # client.logout()
# # # print("Logged out successfully.")