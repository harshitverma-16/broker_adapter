from abc import ABC, abstractmethod

class BaseAdapter(ABC):

    @abstractmethod
    def login(self):
        pass

    @abstractmethod
    def place_order(self, symbol, qty, order_type):
        pass

    @abstractmethod
    def get_orders(self):
        pass

    @abstractmethod
    def cancel_order(self, order_id):
        pass

    @abstractmethod
    def logout(self):
        pass
