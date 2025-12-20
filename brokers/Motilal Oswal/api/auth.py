import requests
import hashlib

LOGIN_URL = "https://invest.motilaloswal.com/OpenAPI/Login"

class MotilalOswalAuthAPI:

    def __init__(self, api_key, api_secret, redirect_url):
        self.api_key = api_key
        self.api_secret = api_secret
        self.redirect_url = redirect_url
        