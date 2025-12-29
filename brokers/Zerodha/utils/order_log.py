import json
from datetime import datetime

from brokers.Zerodha.utils.enum import OrderSide, OrderStatus, OrderType


class OrderLog:
    def __init__(self):
        self.ExchangeOrderId = None
        self.OrderQuantity = 0
        self.OrderPrice = 0.0
        self.OrderSide = OrderSide.None_
        self.OrderType = OrderType.Unknown
        self.OrderStatus = OrderStatus.None_
        self.InstrumentName = None
        self.LeavesQuantity = 0
        self.CumulativeQuantity = 0
        self.OrderTriggerPrice = 0.0
        self.CancelledQuantity = 0
        self.OrderGeneratedDateTime = 0
        self.ExchangeTransactTime = 0
        self.UserText = None  # raw broker JSON for reference

    def to_dict(self):
        return self.__dict__

    def to_json(self):
        return json.dumps(self.to_dict())
