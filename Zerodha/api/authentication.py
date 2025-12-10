class ZerodhaAuthAPI:
    def __init__(self, adapter):
        self.adapter = adapter

    def login(self, api_key, request_token, api_secret):
        data = {
            "api_key": api_key,
            "request_token": request_token,
            "checksum": api_secret
        }
        response = self.adapter._post("/session/token", data)

        # STORE TOKEN INSIDE ADAPTER
        token = response["data"]["access_token"]
        self.adapter.auth_token = token

        return token
