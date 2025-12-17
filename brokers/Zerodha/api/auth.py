import requests
import hashlib

LOGIN_URL = "https://kite.zerodha.com/connect/login"
TOKEN_URL = "https://api.kite.trade/session/token"

class ZerodhaAuthAPI:

    def __init__(self, api_key, api_secret, redirect_url):
        self.api_key = api_key
        self.api_secret = api_secret
        self.redirect_url = redirect_url

    def generate_login_url(self):
        return f"{LOGIN_URL}?v=3&api_key={self.api_key}"

    def exchange_token(self, request_token):
        checksum = hashlib.sha256(
            f"{self.api_key}{request_token}{self.api_secret}".encode()
        ).hexdigest()

        payload = {
            "api_key": self.api_key,
            "request_token": request_token,
            "checksum": checksum
        }

        res = requests.post(TOKEN_URL, data=payload)
        res.raise_for_status()
        return res.json()["data"]["access_token"]
