import requests

class ZerodhaOrderAPI:
    BASE_URL = "https://api.kite.trade"

    def __init__(self, access_token, api_key):
        self.access_token = access_token
        self.api_key = api_key

    def place_order(self, symbol, qty, order_type):
        url = f"{self.BASE_URL}/orders/regular"
        
        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }

        payload = {
            "tradingsymbol": symbol,
            "quantity": qty,
            "transaction_type": order_type,
            "order_type": "MARKET",
            "product": "MIS",
            "exchange": "NSE"
        }

        res = requests.post(url, headers=headers, data=payload)
        res.raise_for_status()
        return res.json()
    
    def cancel_order(self, order_id):
        url = f"{self.BASE_URL}/orders/regular/{order_id}"

        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }

        res = requests.delete(url, headers=headers)
        res.raise_for_status()
        return res.json()
