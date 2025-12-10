from abc import ABC, abstractmethod
import requests
import json



# ------------------------------------------------------------
#  Base Request Models
# ------------------------------------------------------------

class PlaceOrderRequest:
    def __init__(self, symbol, qty, price, side, order_type="MARKET"):
        self.symbol = symbol
        self.qty = qty
        self.price = price
        self.side = side        # BUY / SELL
        self.order_type = order_type


# ------------------------------------------------------------
#  Base Broker REST Adapter
# ------------------------------------------------------------

class BrokerAdapter(ABC):

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.auth_token = None

    # ------------------------------
    #  AUTH
    # ------------------------------
    @abstractmethod
    def login(self, *args, **kwargs):
        """
        Performs login and sets self.auth_token.
        """
        pass

    @abstractmethod
    def logout(self):
        pass

    # ------------------------------
    #  ORDERS
    # ------------------------------
    @abstractmethod
    def place_order(self, order: PlaceOrderRequest):
        pass

    @abstractmethod
    def modify_order(self, order_id, **kwargs):
        pass

    @abstractmethod
    def cancel_order(self, order_id):
        pass

    # ------------------------------
    #  DATA
    # ------------------------------
    @abstractmethod
    def get_positions(self):
        pass

    @abstractmethod
    def get_holdings(self):
        pass

    @abstractmethod
    def get_balance(self):
        pass

    # ------------------------------
    #  Generic HTTP Request Utility
    # ------------------------------
    def _get(self, endpoint, headers=None, params=None):
        url = f"{self.base_url}{endpoint}"
        h = headers or {}
        if self.auth_token:
            h["Authorization"] = f"Bearer {self.auth_token}"

        return self.session.get(url, params=params, headers=h).json()

    def _post(self, endpoint, headers=None, data=None):
        url = f"{self.base_url}{endpoint}"
        h = headers or {"Content-Type": "application/json"}
        if self.auth_token:
            h["Authorization"] = f"Bearer {self.auth_token}"

        return self.session.post(url, data=json.dumps(data), headers=h).json()