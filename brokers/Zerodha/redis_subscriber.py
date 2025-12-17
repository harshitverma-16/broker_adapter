import redis
import json

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True
)

pubsub = redis_client.pubsub()

# Subscribe to channels
pubsub.subscribe(
    "zerodha.auth",
    "zerodha.orders",
    "zerodha.portfolio"
    "zerodha.ticks"
)

print("Listening to Zerodha...")

for message in pubsub.listen():
    if message["type"] == "message":
        data = json.loads(message["data"])
        channel = message["channel"]

        print(f"\n Channel: {channel}")
        print("Payload:", data)
