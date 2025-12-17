from base.base_adapter import BaseAdapter
from api.auth import ZerodhaAuthAPI
from api.order import ZerodhaOrderAPI
from api.portfolio import ZerodhaPortfolioAPI
from utils.redis_publisher import RedisPublisher


class ZerodhaAdapter(BaseAdapter):

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

    # Authentication
    def login(self, request_token):
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

        return self.access_token

    def logout(self):
        self.access_token = None
        self.redis_pub.publish(
            "zerodha.auth",
            {"event": "LOGOUT"}
        )

    def _ensure_login(self):
        if not self.access_token or not self.order_api:
            raise RuntimeError(
                "User not logged in. Call login(request_token) first."
            )

    # Orders API
    def place_order(self, symbol, qty, order_type):
        self._ensure_login()
        response = self.order_api.place_order(symbol, qty, order_type)

        self.redis_pub.publish(
            "zerodha.orders",
            {
                "event": "ORDER_PLACED",
                "request": {
                    "symbol": symbol,
                    "qty": qty,
                    "order_type": order_type
                },
                "response": response
            }
        )
        return response

    def modify_order(self, order_id, order_type, qty, validity):
        self._ensure_login()
        response = self.order_api.modify_order(order_id, order_type, qty, validity)

        self.redis_pub.publish(
            "zerodha.orders",
            {
                "event": "ORDER_MODIFIED",
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
                "event": "ORDER_CANCELLED",
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
