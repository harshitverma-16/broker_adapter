import redis
import json
import uuid
import time
import threading

# --- Configuration ---
CH_REQUESTS = "blitz.requests"
CH_RESPONSES = "blitz.responses"

redis_client = redis.Redis(decode_responses=True)

# --- Listener Thread (Receives replies from Connector) ---
def listen_for_responses():
    pubsub = redis_client.pubsub()
    pubsub.subscribe(CH_RESPONSES)
    print(" [Blitz] Waiting for responses...")
    
    for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            req_id = data.get("request_id")
            status = data.get("status")
            print(f"\n 📩 [Blitz] Response [{req_id}]: {status}")
            print(f"    Data: {data.get('data')}")
            if data.get('error'):
                print(f"    Error: {data.get('error')}")

# Start listening in background
threading.Thread(target=listen_for_responses, daemon=True).start()


# --- Helper to Send Commands ---
def send_command(action, data={}):
    req_id = str(uuid.uuid4())[:8]
    payload = {
        "request_id": req_id,
        "action": action,
        "data": data
    }
    redis_client.publish(CH_REQUESTS, json.dumps(payload))
    print(f"\n 📤 [Blitz] Sending {action} (ID: {req_id})...")
    return req_id


# ==========================================
#  MAIN INTERACTION FLOW
# ==========================================

# 1. Ask for Login URL
send_command("GET_LOGIN_URL")

# Wait a moment for the response to print
time.sleep(1)

print("\n" + "="*50)
print("ACTION REQUIRED: Open the 'login_url' printed above in your browser.")
print("Login, and then copy the 'request_token' from the URL bar.")
print("Example: http://localhost/?request_token=YOUR_TOKEN_IS_HERE&action=login...")
print("="*50 + "\n")

# 2. Input Token Manually (Simulating User)
req_token = input("Paste 'request_token' here: ").strip()

if req_token:
    # 3. Send Login Command
    send_command("LOGIN", {"request_token": req_token})
    time.sleep(2) # Wait for login to finish

    # 4. Fetch Holdings
    send_command("GET_HOLDINGS")
    time.sleep(1)

#     # 5. Place an Order (Blitz Format)
#     # Note: This is a LIMIT order example. Ensure you have funds or change to MARKET.
#     blitz_order = {
#         "correlationOrderId": "test_algo_001",
#         "symbol": "NSE|SBIN",  # Equity Example
#         "quantity": 1,
#         "price": 500.0,        # Limit Price (Should be lower than CMP for Buy)
#         "orderType": "LIMIT",
#         "orderSide": "BUY",
#         "product": "MIS",
#         "tif": "DAY"
#     }
    
#     send_command("PLACE_ORDER", blitz_order)

#     # Keep script running to see final response
#     time.sleep(5)

# else:
#     print("Skipping login...")