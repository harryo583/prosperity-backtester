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
    
        
    def kelp_strategy(self, state: TradingState, take_width: float, make_width: float, midprice_cache_size = 10, vwap_cache_size = 10) -> List[Order]:
        orderbook = state.order_depths.get(KELP)
        position = state.position.get(KELP, 0)
        orders: List[Order] = []
        total_buy_volume = 0
        total_sell_volume = 0
        
        size_threshold = 15
        
        if orderbook.sell_orders and orderbook.buy_orders:
            best_ask_price = min(orderbook.sell_orders.keys())
            best_bid_price = max(orderbook.buy_orders.keys())
            best_ask_volume = -orderbook.sell_orders[best_ask_price]
            best_bid_volume = orderbook.buy_orders[best_bid_price]
            
            voluminous_asks = [
                price for price, vol in orderbook.sell_orders.items() if -vol >= size_threshold
            ]
            
            voluminous_bids = [
                price for price, vol in orderbook.buy_orders.items() if vol >= size_threshold
            ]
            
            market_maker_ask = min(voluminous_asks) if voluminous_asks else best_ask_price
            market_maker_bid = max(voluminous_bids) if voluminous_bids else best_bid_price
            
            filtered_midprice = (market_maker_ask + market_maker_bid) / 2
            self.kelp_midprice_cache.append(filtered_midprice)
            
            vwap_value = (best_bid_price * best_bid_volume + best_ask_price * best_ask_volume) / (best_ask_volume + best_bid_volume)
            self.kelp_vwap_cache.append(vwap_value)
            
            if len(self.kelp_midprice_cache) > midprice_cache_size:
                self.kelp_midprice_cache.pop(0)
            if len(self.kelp_vwap_cache) > vwap_cache_size:
                self.kelp_vwap_cache.pop(0)

            fair_value = filtered_midprice
            
            if best_ask_price <= fair_value - take_width:
                if best_ask_volume <= 20:
                    buy_quantity = min(best_ask_volume, POS_LIMIT_KELP - position)
                    if buy_quantity > 0:
                        orders.append(Order(KELP, best_ask_price, buy_quantity))
                        total_buy_volume += buy_quantity
            
            if best_bid_price >= fair_value + take_width:
                if best_bid_volume  <= 20:
                    sell_quantity = min(best_bid_volume,POS_LIMIT_KELP + position)
                    if sell_quantity > 0:
                        orders.append(Order(KELP, best_bid_price, sell_quantity))
                        total_sell_volume += sell_quantity
            
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
            
            # Determine levels for passive resting orders
            sell_prices_above = [price for price in orderbook.sell_orders.keys() if price > fair_value + 1]
            buy_prices_below = [price for price in orderbook.buy_orders.keys() if price < fair_value - 1]
            
            passive_sell_price = min(sell_prices_above) if sell_prices_above else fair_value + 2
            passive_buy_price = max(buy_prices_below) if buy_prices_below else fair_value - 2
            
            remaining_buy_capacity = POS_LIMIT_KELP - (position + total_buy_volume)
            if remaining_buy_capacity > 0:
                orders.append(Order(KELP, passive_buy_price + 1, remaining_buy_capacity))
            
            remaining_sell_capacity = POS_LIMIT_KELP + (position - total_sell_volume)
            if remaining_sell_capacity > 0:
                orders.append(Order(KELP, passive_sell_price - 1, -remaining_sell_capacity))
        
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
                case "RAINFOREST_RESIN":
                    result[RESIN] = self.resin_strategy(state)
                case _:
                    pass
        
        return result, conversions, traderData