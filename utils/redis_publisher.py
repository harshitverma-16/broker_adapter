import json
import redis


class RedisPublisher:
    def __init__(self, host="localhost", port=6379, db=0):
        self.redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True
        )

    def publish(self, channel: str, message: dict):
        payload = json.dumps(message)
        self.redis.publish(channel, payload)
