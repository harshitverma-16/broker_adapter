from base_adapter import BaseAdapter
from api.auth import ZerodhaAuthAPI
from api.order import ZerodhaOrderAPI
from api.portfolio import ZerodhaPortfolioAPI


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
        self.portfolio_api = ZerodhaPortfolioAPI(self.access_token, self.api_key)

    def logout(self):
        self.access_token = None

    #Order Methods
    def place_order(self, symbol, qty, order_type):
        return self.order_api.place_order(symbol, qty, order_type)
    
    def modify_order(self, order_id, order_type, qty, validity):
        return self.order_api.modify_order(order_id, order_type, qty, validity)
    
    def cancel_order(self, order_id):
        return self.order_api.cancel_order(order_id)

    def get_orders(self):
        return self.order_api.get_orders()
    
    #Portfolio Methods
    def get_holdings(self):
        return self.portfolio_api.get_holdings()
    
    def get_positions(self):
        return self.portfolio_api.get_postions()

    
