from enum import  IntEnum

class OrderSide(IntEnum):
    None_ = 0
    Buy = 49
    Sell = 50

class OrderType(IntEnum):
    Unknown = 0
    Market = 49
    Limit = 50
    Stop = 51
    StopLimit = 52

class OrderStatus(IntEnum):
    None_ = 0
    New = 48
    PartiallyFilled = 49
    Filled = 50
    Cancelled = 52
    Rejected = 56

class TimeInForce(IntEnum):
    None_ = 0
    GFD = 48  # Good for day
    GTC = 49  # Good till cancel
    IOC = 51  # Immediate or cancel
    FOK = 52  # Fill or kill
    GTD = 54  # Good till date
