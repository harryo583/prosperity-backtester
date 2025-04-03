from typing import Dict, List, Tuple
from datamodel import OrderDepth, TradingState, Order
import math

KELP = "KELP"
RESIN = "RAINFOREST_RESIN"

BUY = "BUY"
SELL = "SELL"

POS_LIMIT_KELP = 50
POS_LIMIT_RESIN = 50

class Trader:
    
    
    def __init__(self):
        self.resin_price_cache = []
    
    
    def clear_position_order(
        self,
        orders: List[Order],
        order_book: OrderDepth,
        current_position: int,
        max_position: int,
        product: str,
        total_buy_volume: int,
        total_sell_volume: int,
        reference_price: float,
    ) -> Tuple[int, int]:
        net_position_after_trades = current_position + total_buy_volume - total_sell_volume
        clearing_bid_price = math.floor(reference_price)
        clearing_ask_price = math.ceil(reference_price)

        available_buy_capacity = max_position - (current_position + total_buy_volume)
        available_sell_capacity = max_position + (current_position - total_sell_volume)

        # If net long, try to sell at the clearing ask price
        if net_position_after_trades > 0:
            if clearing_ask_price in order_book.buy_orders:
                clear_volume = min(order_book.buy_orders[clearing_ask_price], net_position_after_trades)
                trade_volume = min(available_sell_capacity, clear_volume)
                orders.append(Order(product, clearing_ask_price, -abs(trade_volume)))
                total_sell_volume += abs(trade_volume)

        # If net short, try to buy at the clearing bid price
        if net_position_after_trades < 0:
            if clearing_bid_price in order_book.sell_orders:
                clear_volume = min(abs(order_book.sell_orders[clearing_bid_price]), abs(net_position_after_trades))
                trade_volume = min(available_buy_capacity, clear_volume)
                orders.append(Order(product, clearing_bid_price, abs(trade_volume)))
                total_buy_volume += abs(trade_volume)

        return total_buy_volume, total_sell_volume
    

    def resin_strategy(self, state: TradingState) -> List[Order]:
        orderbook = state.order_depths.get(RESIN)
        position = state.position.get(RESIN, 0)
        reference_price = 10000
        orders: List[Order] = []
        total_buy_volume = 0
        total_sell_volume = 0

        # Determine price levels for resting orders
        lowest_sell_above_threshold = min(
            [price for price in orderbook.sell_orders.keys() if price > reference_price + 1]
        )
        highest_buy_below_threshold = max(
            [price for price in orderbook.buy_orders.keys() if price < reference_price - 1]
        )

        # Take liquidity on the buy side if the best ask is below the reference price
        if orderbook.sell_orders:
            best_ask_price = min(orderbook.sell_orders.keys())
            best_ask_volume = -orderbook.sell_orders[best_ask_price]
            if best_ask_price < reference_price:
                buy_quantity = min(best_ask_volume, POS_LIMIT_RESIN - position)
                if buy_quantity > 0:
                    orders.append(Order(RESIN, best_ask_price, buy_quantity))
                    total_buy_volume += buy_quantity

        # Take liquidity on the sell side if the best bid is above the reference price
        if orderbook.buy_orders:
            best_bid_price = max(orderbook.buy_orders.keys())
            best_bid_volume = orderbook.buy_orders[best_bid_price]
            if best_bid_price > reference_price:
                sell_quantity = min(best_bid_volume, POS_LIMIT_RESIN + position)
                if sell_quantity > 0:
                    orders.append(Order(RESIN, best_bid_price, -sell_quantity))
                    total_sell_volume += sell_quantity

        # Clear net positions if needed
        total_buy_volume, total_sell_volume = self.clear_position_order(
            orders,
            orderbook,
            position,
            POS_LIMIT_RESIN,
            RESIN,
            total_buy_volume,
            total_sell_volume,
            reference_price,
        )

        # Place additional passive orders to make liquidity
        remaining_buy_capacity = POS_LIMIT_RESIN - (position + total_buy_volume)
        if remaining_buy_capacity > 0:
            orders.append(Order(RESIN, highest_buy_below_threshold + 1, remaining_buy_capacity))

        remaining_sell_capacity = POS_LIMIT_RESIN + (position - total_sell_volume)
        if remaining_sell_capacity > 0:
            orders.append(Order(RESIN, lowest_sell_above_threshold - 1, -remaining_sell_capacity))

        return orders
    
    
    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        result = {}
        traderData = "SAMPLE" 
        conversions = 1
        
        for product in state.order_depths:
            if product == RESIN:
                result[RESIN] = self.resin_strategy(state)
        
        return result, conversions, traderData