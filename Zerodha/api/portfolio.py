import requests

class ZerodhaPortfolioAPI:

    BASE_URL = "https://api.kite.trade"
    
    def __init__(self, access_token, api_key):
        self.access_token = access_token
        self.api_key = api_key

    # Get Holdings
    def get_holdings(self):
        url = f"{self.BASE_URL}/portfolio/holdings"

        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }

        res = requests.get(url, headers= headers)
        res.raise_for_status()
        return res.json()
    
    # Get Positions
    def get_postions(self):
        url = f"{self.BASE_URL}/portfolio/positions"

        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }

        res = requests.get(url, headers= headers)
        res.raise_for_status()
        return res.json()
        