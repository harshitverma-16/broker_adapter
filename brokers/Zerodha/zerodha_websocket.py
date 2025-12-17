import asyncio
import json
import struct
import signal
import websockets
from typing import List, Optional

WS_URL = "wss://ws.kite.trade"

MODE_LTP = "ltp"
MODE_QUOTE = "quote"
MODE_FULL = "full"


class ZerodhaWebSocket:
    def __init__(self, api_key: str, access_token: str):
        self.url = f"{WS_URL}?api_key={api_key}&access_token={access_token}"
        self.ws: Optional[websockets.WebSocketClientProtocol] = None

        self.connected = asyncio.Event()
        self.should_run = True

        self.tokens: List[int] = []
        self.mode = MODE_LTP


    # Start websocket 

    async def start(self):
        while self.should_run:
            try:
                await self.connect()
                await self.listen()
            except Exception as exc:
                print(f"WebSocket error: {exc}")
            finally:
                self.connected.clear()
                if self.ws:
                    await self.ws.close()
                await asyncio.sleep(3)


    # Connect

    async def connect(self):
        self.ws = await websockets.connect(
            self.url,
            ping_interval=20,
            ping_timeout=10,
            compression=None
        )
        self.connected.set()

        if self.tokens:
            await self.subscribe(self.tokens, self.mode)


    # Subscribe

    async def subscribe(self, tokens: List[int], mode=MODE_LTP):
        await self.connected.wait()

        self.tokens = tokens
        self.mode = mode

        await self.ws.send(json.dumps({
            "a": "subscribe",
            "v": tokens
        }))

        await self.ws.send(json.dumps({
            "a": "mode",
            "v": [mode, tokens]
        }))


    # Listen

    async def listen(self):
        async for message in self.ws:
            if isinstance(message, bytes):
                for tick in self.parse_binary(message):
                    if tick:
                        print(tick)
            else:
                self.handle_text(message)


    # Handle text messages
    def handle_text(self, message: str):
        try:
            data = json.loads(message)
            if data.get("type") == "error":
                print(f"Error message: {data}")
        except json.JSONDecodeError:
            pass


    # Binary parsing

    def parse_binary(self, packet: bytes):
        ticks = []
        offset = 0

        if len(packet) < 2:
            return ticks

        num_packets = struct.unpack_from(">H", packet, offset)[0]
        offset += 2

        for _ in range(num_packets):
            if offset + 2 > len(packet):
                break

            pkt_len = struct.unpack_from(">H", packet, offset)[0]
            offset += 2

            pkt = packet[offset: offset + pkt_len]
            offset += pkt_len

            tick = self.parse_tick(pkt)
            ticks.append(tick)

        return ticks

    def parse_tick(self, pkt: bytes):
        if len(pkt) < 8:
            return None

        instrument_token = struct.unpack_from(">I", pkt, 0)[0]
        last_price = struct.unpack_from(">I", pkt, 4)[0] / 100

        if len(pkt) == 8:
            return {
                "instrument_token": instrument_token,
                "mode": "LTP",
                "last_price": last_price
            }

        if len(pkt) == 44:
            volume = struct.unpack_from(">I", pkt, 8)[0]
            return {
                "instrument_token": instrument_token,
                "mode": "QUOTE",
                "last_price": last_price,
                "volume": volume
            }

        if len(pkt) == 184:
            volume = struct.unpack_from(">I", pkt, 8)[0]
            open_interest = struct.unpack_from(">I", pkt, 12)[0]
            return {
                "instrument_token": instrument_token,
                "mode": "FULL",
                "last_price": last_price,
                "volume": volume,
                "open_interest": open_interest
            }

        return None


    # Stop

    async def stop(self):
        self.should_run = False
        if self.ws:
            await self.ws.close()

