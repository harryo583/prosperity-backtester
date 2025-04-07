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
        
    def kelp_strategy(self, state: TradingState, take_width: float, make_width: float, midprice_cache_size=10, vwap_cache_size=10) -> List[Order]:
        orderbook = state.order_depths.get(KELP)
        position = state.position.get(KELP, 0)
        orders: List[Order] = []
        total_buy_volume = 0
        total_sell_volume = 0

        if orderbook.sell_orders and orderbook.buy_orders:
            best_ask_price = min(orderbook.sell_orders.keys())
            best_bid_price = max(orderbook.buy_orders.keys())
            best_ask_volume = -orderbook.sell_orders[best_ask_price]
            best_bid_volume = orderbook.buy_orders[best_bid_price]

            midprice = (best_ask_price + best_bid_price) / 2
            vwap = (best_bid_price * best_bid_volume + best_ask_price * best_ask_volume) / (best_ask_volume + best_bid_volume)
            
            self.kelp_midprice_cache.append(midprice)
            self.kelp_vwap_cache.append(vwap)
            if len(self.kelp_midprice_cache) > midprice_cache_size:
                self.kelp_midprice_cache.pop(0)
            if len(self.kelp_vwap_cache) > vwap_cache_size:
                self.kelp_vwap_cache.pop(0)

            fair_value = sum(self.kelp_midprice_cache) / len(self.kelp_midprice_cache)
            vwap_trend = vwap - fair_value

            # Inventory-aware skew adjustment
            inventory_skew = -position / POS_LIMIT_KELP * make_width  # e.g. +ve if short, pushing price down to attract buys
            trend_skew = vwap_trend * 0.5  # dampen market trend influence

            skewed_fair_value = fair_value + inventory_skew + trend_skew

            spread = make_width
            if abs(position) > POS_LIMIT_KELP * 0.75:
                spread *= 1.5  # widen more when inventory is stretched

            bid_price = round(skewed_fair_value - spread / 2)
            ask_price = round(skewed_fair_value + spread / 2)

            remaining_buy_capacity = POS_LIMIT_KELP - position - total_buy_volume
            remaining_sell_capacity = POS_LIMIT_KELP + position - total_sell_volume

            # Imbalanced quoting: size based on position room
            bid_size = max(1, min(remaining_buy_capacity, 15))
            ask_size = max(1, min(remaining_sell_capacity, 15))

            if remaining_buy_capacity > 0:
                orders.append(Order(KELP, bid_price, bid_size))
                total_buy_volume += bid_size

            if remaining_sell_capacity > 0:
                orders.append(Order(KELP, ask_price, -ask_size))
                total_sell_volume += ask_size

            # Aggressive take if mispricing exists
            if best_ask_price <= fair_value - take_width and remaining_buy_capacity > 0:
                qty = min(best_ask_volume, remaining_buy_capacity)
                orders.append(Order(KELP, best_ask_price, qty))
                total_buy_volume += qty

            if best_bid_price >= fair_value + take_width and remaining_sell_capacity > 0:
                qty = min(best_bid_volume, remaining_sell_capacity)
                orders.append(Order(KELP, best_bid_price, -qty))
                total_sell_volume += qty

            # Final inventory flattening if far from fair value
            total_buy_volume, total_sell_volume = self.clear_position_order(
                orders,
                orderbook,
                position,
                POS_LIMIT_KELP,
                KELP,
                total_buy_volume,
                total_sell_volume,
                fair_value
            )

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
                case "KELP":
                    result[KELP] = self.kelp_strategy(state, take_width=1, make_width=3.5)
                case _:
                    pass
        
        return result, conversions, traderData