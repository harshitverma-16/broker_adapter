from abc import ABC, abstractmethod

class BaseAdapter(ABC):

    @abstractmethod
    def login(self):
        pass

    @abstractmethod
    def place_order(self, symbol, qty, order_type):
        pass

    @abstractmethod
    def get_positions(self):
        pass

    @abstractmethod
    def logout(self):
        pass
