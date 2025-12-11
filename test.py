from Zerodha.api.zerodha_adapter import ZerodhaAdapter

api_key = "xxx"
api_secret = "yyy"
redirect_url = "http://localhost"  # Your redirect URL

adapter = ZerodhaAdapter(api_key, api_secret, redirect_url)

print("Login URL:", adapter.auth_api.generate_login_url())

# After user logs in request_token arrives to redirect_url
request_token = "token_from_zerodha"  # Replace with actual token

adapter.login(request_token)

response = adapter.place_order("INFY", 1, "BUY")
print(response)
