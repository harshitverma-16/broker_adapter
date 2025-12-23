import requests

class ZerodhaOrderAPI:
    BASE_URL = "https://api.kite.trade"

    def __init__(self, access_token, api_key):
        self.access_token = access_token
        self.api_key = api_key

    # Place Order
    def place_order(self, symbol, qty, order_type, transaction_type, product, exchange, validity, price, trigger_price):
        url = f"{self.BASE_URL}/orders/regular"
        
        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }

        payload = {
            "tradingsymbol": symbol,
            "exchange": exchange,
            "transaction_type": transaction_type,
            "order_type": order_type,
            "quantity": qty,
            "product": product,
            "price" : price,
            "trigger_price": trigger_price,
            "validity": validity
        }

        res = requests.post(url, headers=headers, data=payload)
        res.raise_for_status()
        return res.json()
    
    
    # Modify Order
    def modify_order(self, order_id, order_type, qty, validity):
        url = f"{self.BASE_URL}/orders/regular/{order_id}"

        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }

        payload = {
            "order_type": order_type,
            "quantity": qty,
            "validity": validity
        }

        res = requests.put(url, headers=headers, data=payload)
        res.raise_for_status()
        return res.json()
    

    # Cancel Order
    def cancel_order(self, order_id):
        url = f"{self.BASE_URL}/orders/regular/{order_id}"

        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }

        res = requests.delete(url, headers=headers)
        res.raise_for_status()
        return res.json()     # change to the appropriate response
    

    # Retrieve Orders
    def get_orders(self):
        url = f"{self.BASE_URL}/orders"

        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }

        res = requests.get(url, headers=headers)
        res.raise_for_status()
        return res.json()
    

    def get_order_history(self, order_id):
        url = f"{self.BASE_URL}/orders/{order_id}"
        headers = {
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }
         
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        return res.json()
