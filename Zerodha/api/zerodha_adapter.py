from base_adapter import BaseAdapter
from api.auth import ZerodhaAuthAPI
from order import ZerodhaOrderAPI

class ZerodhaAdapter(BaseAdapter):

    def __init__(self, api_key, api_secret, redirect_url):
        self.api_key = api_key
        self.api_secret = api_secret
        self.redirect_url = redirect_url

        self.auth_api = ZerodhaAuthAPI(api_key, api_secret, redirect_url)
        self.order_api = None
        self.access_token = None

    def login(self, request_token):
        self.access_token = self.auth_api.exchange_token(request_token)
        self.order_api = ZerodhaOrderAPI(self.access_token, self.api_key)

    def place_order(self, symbol, qty, order_type):
        return self.order_api.place_order(symbol, qty, order_type)

    def get_positions(self):
        pass

    def logout(self):
        self.access_token = None
