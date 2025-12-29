from datetime import datetime
import json
import logging
from brokers.Zerodha.utils.order_log import OrderLog

class BrokerOrderMapper:
    """
    Converts broker-specific order events into Blitz OrderLog
    """

    @staticmethod
    def map(broker_name: str, raw_data) -> OrderLog:
        """raw_data should be a dict, not a string"""
        order_log = OrderLog()
        try:
            data = raw_data if isinstance(raw_data, dict) else json.loads(raw_data)

            if broker_name.lower() == "zerodha":
                BrokerOrderMapper._map_zerodha(data, order_log)
            elif broker_name.lower() == "motilal":
                BrokerOrderMapper._map_motilal(data, order_log)
            else:
                raise ValueError(f"Unsupported broker: {broker_name}")

            # Store the original dict directly (not as a JSON string)
            order_log.UserText = data

        except Exception as e:
            logging.error(f"[OrderLog Mapper Error] {e}")

        return order_log
    def to_json(self):
    # Instead of doing json.dumps(self.UserText) blindly
        data = {
            "ExchangeOrderId": self.ExchangeOrderId,
            "OrderQuantity": self.OrderQuantity,
            "OrderPrice": self.OrderPrice,
            "OrderSide": self.OrderSide,
            "OrderType": self.OrderType,
            "OrderStatus": self.OrderStatus,
            "InstrumentName": self.InstrumentName,
            "LeavesQuantity": self.LeavesQuantity,
            "CumulativeQuantity": self.CumulativeQuantity,
            "OrderTriggerPrice": self.OrderTriggerPrice,
            "CancelledQuantity": getattr(self, "CancelledQuantity", 0),
            "OrderGeneratedDateTime": self.OrderGeneratedDateTime,
            "ExchangeTransactTime": self.ExchangeTransactTime,
            "AverageTradedPrice": self.AverageTradedPrice,
            # Directly include the dict
            "UserText": self.UserText,
        }
        return json.dumps(data) 

    # ─────────────────────────────
    # ZERODHA
    # ─────────────────────────────
    @staticmethod
    def _map_zerodha(data: dict, o: OrderLog):
        details = data.get("details", {})

        o.ExchangeOrderId = details.get("exchange_order_id")
        o.ExecutionId = data.get("order_id")
        o.Account = details.get("account_id")

        o.InstrumentName = details.get("tradingsymbol")
        o.InstrumentId = details.get("instrument_token", 0)

        o.OrderQuantity = details.get("quantity", 0)
        o.OrderPrice = details.get("price", 0.0)
        o.OrderTriggerPrice = details.get("trigger_price", 0.0)

        o.CumulativeQuantity = details.get("filled_quantity", 0)
        o.LeavesQuantity = details.get("pending_quantity", 0)

        # Use strings directly instead of enums
        o.OrderSide = details.get("transaction_type", "").upper()  # "BUY" or "SELL"
        o.OrderType = details.get("order_type", "").upper()        # "LIMIT" or "MARKET"
        o.OrderStatus = details.get("status", "").upper()          # "OPEN", "CANCELLED", etc.

        o.AverageTradedPrice = details.get("average_price", 0.0)
        o.OrderGeneratedDateTime = BrokerOrderMapper._to_epoch(details.get("order_timestamp"))
        o.ExchangeTransactTime = BrokerOrderMapper._to_epoch(details.get("exchange_timestamp"))

    # ─────────────────────────────
    # MOTILAL (placeholder)
    # ─────────────────────────────
    @staticmethod
    def _map_motilal(data: dict, o: OrderLog):
        o.ExchangeOrderId = data.get("exchange_order_id")
        o.InstrumentName = data.get("symbol")
        o.OrderQuantity = data.get("qty", 0)
        o.OrderPrice = data.get("price", 0.0)
        o.OrderSide = data.get("transaction_type", "")
        o.OrderType = data.get("order_type", "")
        o.OrderStatus = data.get("status", "")

    # ─────────────────────────────
    # HELPERS
    # ─────────────────────────────
    @staticmethod
    def _map_status(status: str) -> str:
        mapping = {
            "OPEN": "NEW",
            "COMPLETE": "FILLED",
            "CANCELLED": "CANCELLED",
            "REJECTED": "REJECTED",
        }
        return mapping.get(status, "NEW")

    @staticmethod
    def _to_epoch(ts: str) -> int:
        if not ts:
            return 0
        return int(datetime.fromisoformat(ts).timestamp() * 1000)
