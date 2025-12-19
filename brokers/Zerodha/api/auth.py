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
    





#     # ------------------------Testing-----------------------------
# my_api_key = "2i4ayyawcrptt24h" 
# my_api_secret = "2lxel09zt42jim5veokpgg6slrih2fpa"

# # Create an object of the class
# zerodha = ZerodhaAuthAPI(my_api_key, my_api_secret, "http://localhost")

# print("--- Zerodha Login Flow ---")

# # GET LOGIN URL
# login_link = zerodha.generate_login_url()
# print(f"1. Open this URL :\n{login_link}")

# # INPUT
# req_token = input("\n2. Paste the 'request_token' from the browser URL here: ").strip()

# # 4. VERIFY AUTHENTICATION
# if req_token:
#     try:
#         access_token = zerodha.exchange_token(req_token)
#         print("\nSUCCESS! Authentication successful.")
#         print(f"Access Token: {access_token}")
#         print("(successful working)")
#     except Exception as e:
#         print(f"\nERROR: {e}")
# else:
#     print("\nNo token provided.")