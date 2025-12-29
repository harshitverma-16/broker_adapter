import requests


class MotilalOrderAPI:
    BASE_URL = "https://openapi.motilaloswal.com"

    def __init__(self, api_key, client_code, jwt_token):
        self.api_key = api_key
        self.client_code = client_code
        self.jwt_token = jwt_token

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.jwt_token}",
            "ApiKey": self.api_key,
            "ClientCode": self.client_code
        }

    # -------------------------------------------------
    # PLACE ORDER (Original Motilal Format)
    # -------------------------------------------------
    def place_order(
        self,
        symbol,
        exchange,
        side,
        quantity,
        order_type,
        product_type,
        price=0,
        trigger_price=0,
        validity="DAY"
    ):
        url = f"{self.BASE_URL}/rest/trans/v1/placeorder"

        payload = {
            "clientcode": self.client_code,
            "exchange": exchange,            # NSE / BSE / NFO
            "symboltoken": symbol,            # MO Symbol Token
            "buyorsell": side,                # BUY / SELL
            "ordertype": order_type,          # MARKET / LIMIT / SL / SL-M
            "producttype": product_type,      # MIS / CNC / NRML
            "quantity": quantity,
            "price": price,
            "triggerprice": trigger_price,
            "validity": validity              # DAY / IOC
        }

        res = requests.post(
            url,
            headers=self._headers(),
            json=payload
        )
        res.raise_for_status()
        return res.json()

    # -------------------------------------------------
    # MODIFY ORDER
    # -------------------------------------------------
    def modify_order(
        self,
        order_id,
        quantity,
        price=0,
        trigger_price=0
    ):
        url = f"{self.BASE_URL}/rest/trans/v1/modifyorder"

        payload = {
            "clientcode": self.client_code,
            "orderid": order_id,
            "quantity": quantity,
            "price": price,
            "triggerprice": trigger_price
        }

        res = requests.post(
            url,
            headers=self._headers(),
            json=payload
        )
        res.raise_for_status()
        return res.json()

    # -------------------------------------------------
    # CANCEL ORDER
    # -------------------------------------------------
    def cancel_order(self, order_id):
        url = f"{self.BASE_URL}/rest/trans/v1/cancelorder"

        payload = {
            "clientcode": self.client_code,
            "orderid": order_id
        }

        res = requests.post(
            url,
            headers=self._headers(),
            json=payload
        )
        res.raise_for_status()
        return res.json()

    # -------------------------------------------------
    # ORDER BOOK
    # -------------------------------------------------
    def get_orders(self):
        url = f"{self.BASE_URL}/rest/trans/v1/orderbook"

        payload = {
            "clientcode": self.client_code
        }

        res = requests.post(
            url,
            headers=self._headers(),
            json=payload
        )
        res.raise_for_status()
        return res.json()

    # -------------------------------------------------
    # ORDER HISTORY
    # -------------------------------------------------
    def get_order_history(self, order_id):
        url = f"{self.BASE_URL}/rest/trans/v1/orderhistory"

        payload = {
            "clientcode": self.client_code,
            "orderid": order_id
        }

        res = requests.post(
            url,
            headers=self._headers(),
            json=payload
        )
        res.raise_for_status()
        return res.json()
