class ZerodhaMarginAPI:
    def __init__(self, adapter):
        self.adapter = adapter

    def get_balance(self):
        return self.adapter._get("/user/margins")

    def get_margins_equity(self):
        return self.adapter._get("/user/margins/equity")
