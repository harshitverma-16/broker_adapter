class ZerodhaOrderAPI:
    def __init__(self, adapter):
        self.adapter = adapter

    def place_order(self, order):
        data = {
            "tradingsymbol": order.symbol,
            "quantity": order.qty,
            "price": order.price,
            "transaction_type": order.side,
            "order_type": order.order_type
        }
        return self.adapter._post("/orders/regular", data)

    def cancel_order(self, order_id):
        return self.adapter._post(f"/orders/{order_id}/cancel")
