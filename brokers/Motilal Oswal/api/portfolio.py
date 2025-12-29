import requests


class MotilalOswalPortfolioAPI:
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
    # HOLDINGS (Original MO Endpoint)
    # -------------------------------------------------
    def get_holdings(self):
        url = f"{self.BASE_URL}/rest/portfolio/v1/holdings"

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
    # POSITIONS (Original MO Endpoint)
    # -------------------------------------------------
    def get_positions(self):
        url = f"{self.BASE_URL}/rest/portfolio/v1/positions"

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
