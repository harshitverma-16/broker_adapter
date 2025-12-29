import requests
import hashlib
import json

LOGIN_URL = "https://invest.motilaloswal.com/OpenAPI/Login"


class MotilalOswalAuthAPI:
    """
    Motilal Oswal OpenAPI Authentication
    """

    def __init__(self, api_key, api_secret, client_code, password, dob):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client_code = client_code
        self.password = password
        self.dob = dob  # Format: DDMMYYYY

    # -------------------------------------------------
    # Generate Checksum (MANDATORY in MO)
    # -------------------------------------------------
    def _generate_checksum(self):
        """
        checksum = SHA256(api_key + client_code + password + dob + api_secret)
        """
        raw_string = (
            self.api_key +
            self.client_code +
            self.password +
            self.dob +
            self.api_secret
        )

        return hashlib.sha256(raw_string.encode("utf-8")).hexdigest()

    # -------------------------------------------------
    # LOGIN
    # -------------------------------------------------
    def login(self):
        payload = {
            "ApiKey": self.api_key,
            "ClientCode": self.client_code,
            "Password": self.password,
            "DOB": self.dob,
            "Checksum": self._generate_checksum()
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = requests.post(
            LOGIN_URL,
            headers=headers,
            json=payload,
            timeout=10
        )

        response.raise_for_status()
        data = response.json()

        # Typical MO Response
        # {
        #   "Status": "SUCCESS",
        #   "AuthToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        #   "ClientCode": "AB1234",
        #   "Message": "Login successful"
        # }

        if data.get("Status") != "SUCCESS":
            raise RuntimeError(f"Motilal Login Failed: {data}")

        return {
            "jwt_token": data.get("AuthToken"),
            "client_code": data.get("ClientCode"),
            "raw": data
        }
