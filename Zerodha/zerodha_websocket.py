import asyncio
import json
import struct
import time
import websockets
from typing import List, Dict, Callable
from utils.redis_publisher import RedisPublisher


class ZerodhaWebSocket:

    WS_URL = "wss://ws.kite.trade"
    MODE_LTP = "ltp"

    def __init__(self, api_key, access_token):
        self.url = f"{self.WS_URL}?api_key={api_key}&access_token={access_token}"
        self.redis_pub = RedisPublisher()
        self.websocket = None
        self.subscribed_tokens = []

    async def connect(self):
        self.websocket = await websockets.connect(
            self.url,
            ping_interval=None,
            compression=None
        )
        print("Zerodha WebSocket connected")

        await self.listen()

    async def subscribe(self, tokens: List[int]):
        self.subscribed_tokens = tokens

        await self.websocket.send(json.dumps({
            "a": "subscribe",
            "v": tokens
        }))

        await self.websocket.send(json.dumps({
            "a": "mode",
            "v": ["ltp", tokens]
        }))

        print("Subscribed to tokens")

    async def listen(self):
        while True:
            message = await self.websocket.recv()

            if isinstance(message, bytes) and len(message) == 1:
                continue  # heartbeat

            ticks = self.parse_binary(message)
            for tick in ticks:
                self.redis_pub.publish("zerodha.ticks", tick)

    def parse_binary(self, data: bytes) -> List[Dict]:
        ticks = []

        packet_count = struct.unpack(">H", data[:2])[0]
        offset = 2

        for _ in range(packet_count):
            length = struct.unpack(">H", data[offset:offset + 2])[0]
            offset += 2

            packet = data[offset:offset + length]
            offset += length

            if len(packet) == 8:
                token = struct.unpack(">I", packet[:4])[0]
                price = struct.unpack(">i", packet[4:8])[0] / 100.0

                ticks.append({
                    "instrument_token": token,
                    "ltp": price,
                    "timestamp": int(time.time() * 1000)
                })

        return ticks
