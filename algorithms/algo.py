from typing import Dict, List, Tuple
from datamodel import OrderDepth, TradingState, Order
import math

KELP = "KELP"
RESIN = "RAINFOREST_RESIN"
SQUID_INK = "SQUID_INK"

BUY = "BUY"
SELL = "SELL"

POS_LIMIT_KELP = 50
POS_LIMIT_RESIN = 50
POS_LIMIT_SQUID_INK = 50

class Trader:
    
    def __init__(self):
        self.kelp_midprice_cache = []
        self.kelp_vwap_cache = []
    
    def clear_position_order(
        self,
        orders: List[Order],
        order_book: OrderDepth,
        current_position: int,
        max_position: int,
        product: str,
        accumulated_buy_volume: int,
        accumulated_sell_volume: int,
        reference_price: float,
    ) -> Tuple[int, int]:
        net_position_after_trades = current_position + accumulated_buy_volume - accumulated_sell_volume
        clearing_bid_price = math.floor(reference_price)
        clearing_ask_price = math.ceil(reference_price)

        available_buy_capacity = max_position - (current_position + accumulated_buy_volume)
        available_sell_capacity = max_position + (current_position - accumulated_sell_volume)

        # If net long, try to sell at the clearing ask price
        if net_position_after_trades > 0:
            if clearing_ask_price in order_book.buy_orders:
                clear_volume = min(order_book.buy_orders[clearing_ask_price], net_position_after_trades)
                trade_volume = min(available_sell_capacity, clear_volume)
                orders.append(Order(product, clearing_ask_price, -abs(trade_volume)))
                accumulated_sell_volume += abs(trade_volume)

        # If net short, try to buy at the clearing bid price
        if net_position_after_trades < 0:
            if clearing_bid_price in order_book.sell_orders:
                clear_volume = min(abs(order_book.sell_orders[clearing_bid_price]), abs(net_position_after_trades))
                trade_volume = min(available_buy_capacity, clear_volume)
                orders.append(Order(product, clearing_bid_price, abs(trade_volume)))
                accumulated_buy_volume += abs(trade_volume)

        return accumulated_buy_volume, accumulated_sell_volume
    
    
    def squid_ink_strategy(self, state):
        orderbook = state.order_depths.get(SQUID_INK)
        position = state.position.get(SQUID_INK, 0)
        orders: List[Order] = []
        
        return orders
    

    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        """
        Takes all orders for all symbols as an input and outputs a list of orders to be sent
        """
        result = {}
        traderData = "SAMPLE" 
        conversions = 1
        
        for product in state.order_depths:
            match product:
                case "SQUID_INK":
                    result[SQUID_INK] = self.squid_ink_strategy(state)
                case _:
                    pass
        
        return result, conversions, traderData