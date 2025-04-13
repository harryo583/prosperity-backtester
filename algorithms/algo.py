from typing import Dict, List, Tuple
from datamodel import OrderDepth, TradingState, Order
import json
import math

PRODUCTS = ["RAINFOREST_RESIN", "KELP", "SQUID_INK", "CROISSANTS", "DJEMBES", "JAMS", "PICNIC_BASKET1", "PICNIC_BASKET2"]

RESIN = "RAINFOREST_RESIN"
KELP = "KELP"
SQUID_INK = "SQUID_INK"
CROISSANTS = "CROISSANTS"
DJEMBES = "DJEMBES"
JAMS = "JAMS"
PCB1 = "PICNIC_BASKET1"
PCB2 = "PICNIC_BASKET2"

POSITION_LIMITS = {
    RESIN: 50,
    KELP: 50,
    SQUID_INK: 50,
    CROISSANTS: 250,
    JAMS: 350,
    DJEMBES: 60,
    PCB1: 60,
    PCB2: 100
}

BUY = "BUY"
SELL = "SELL"

THRESHOLD_LOW = -2.0
THRESHOLD_HIGH = 2.0
WINDOW_SIZE = 50
SQUID_POSITION_LIMIT = 50

class Trader:
    
    def __init__(self):
        self.kelp_midprice_cache = []
        self.kelp_vwap_cache = []
        self.mid_prices_cache = []

    def calculate_stats(self, prices: List[float]) -> float:
        if not prices:
            return -1
        mean_price = sum(prices) / len(prices)
        variance = sum((x - mean_price) ** 2 for x in prices) / len(prices)
        std = math.sqrt(variance)
        return mean_price, std
        

    def squid_try(self, state: TradingState) -> List[Order]:
        orders: List[Order] = []
        order_depth = state.order_depths.get(SQUID_INK)
        if not order_depth:
            return orders
        
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        if not best_bid or not best_ask:
            return orders
        
        midprice = (best_bid + best_ask) / 2
        if len(self.mid_prices_cache) < WINDOW_SIZE:
            self.mid_prices_cache.append(midprice)
            return orders
        
        mean, std = self.calculate_stats(self.mid_prices_cache)
        if std==0:
            return orders
        z_score = (midprice - mean) / std 

        if z_score > THRESHOLD_HIGH:
            # sell enough to get our position to -50
            orders.append(Order(SQUID_INK, best_bid, -1))
            return orders
        elif z_score < THRESHOLD_LOW:
            # buy enough to get our position to 50
            orders.append(Order(SQUID_INK, best_ask, 1))
            return orders

        self.mid_prices_cache.append(midprice)
        if len(self.mid_prices_cache) > WINDOW_SIZE:
            self.mid_prices_cache.pop(0)
        return orders

    
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
        filtered_sell_orders = [price for price in orderbook.sell_orders.keys() if price > reference_price + 1]
        filtered_buy_orders = [price for price in orderbook.buy_orders.keys() if price < reference_price - 1]
        
        if not filtered_sell_orders or not filtered_buy_orders:
            return []
        
        lowest_sell_above_threshold = min(filtered_sell_orders)
        highest_buy_below_threshold = max(filtered_buy_orders)

        # Take liquidity on the buy side if the best ask is below the reference price
        if orderbook.sell_orders:
            best_ask_price = min(orderbook.sell_orders.keys())
            best_ask_volume = -orderbook.sell_orders[best_ask_price]
            if best_ask_price < reference_price:
                buy_quantity = min(best_ask_volume, POSITION_LIMITS[RESIN] - position)
                if buy_quantity > 0:
                    orders.append(Order(RESIN, best_ask_price, buy_quantity))
                    total_buy_volume += buy_quantity

        # Take liquidity on the sell side if the best bid is above the reference price
        if orderbook.buy_orders:
            best_bid_price = max(orderbook.buy_orders.keys())
            best_bid_volume = orderbook.buy_orders[best_bid_price]
            if best_bid_price > reference_price:
                sell_quantity = min(best_bid_volume, POSITION_LIMITS[RESIN] + position)
                if sell_quantity > 0:
                    orders.append(Order(RESIN, best_bid_price, -sell_quantity))
                    total_sell_volume += sell_quantity

        # Clear net positions if needed
        total_buy_volume, total_sell_volume = self.clear_position_order(
            orders,
            orderbook,
            position,
            POSITION_LIMITS[RESIN],
            RESIN,
            total_buy_volume,
            total_sell_volume,
            reference_price,
        )

        # Place additional passive orders to make liquidity
        remaining_buy_capacity = POSITION_LIMITS[RESIN] - (position + total_buy_volume)
        if remaining_buy_capacity > 0:
            orders.append(Order(RESIN, highest_buy_below_threshold + 1, remaining_buy_capacity))

        remaining_sell_capacity = POSITION_LIMITS[RESIN] + (position - total_sell_volume)
        if remaining_sell_capacity > 0:
            orders.append(Order(RESIN, lowest_sell_above_threshold - 1, -remaining_sell_capacity))

        return orders
    
    
    def calculate_resin_price(self, order_depth: OrderDepth) -> float:
        # Midprice strategy for stable product
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else 0
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else 0
        return (best_bid + best_ask) / 2 if best_bid and best_ask else 10


    def calculate_kelp_price(self, order_depth: OrderDepth, timestamp: int) -> float:
        # EMA strategy with 5-period window
        price_history = self.kelp_midprice_cache
        if not price_history:
            return self.calculate_resin_price(order_depth)  # Fallback if no data
        
        # EMA parameters
        n = 5  # Window size
        alpha = 2 / (n + 1)  # Smoothing factor
        
        # Start with SMA for first value
        if len(price_history) <= n:
            return sum(price_history) / len(price_history)
        
        # Calculate EMA for subsequent values
        ema = price_history[0]  # Start with first price
        for price in price_history[1:]:
            ema = alpha * price + (1 - alpha) * ema
        
        return ema
    
        
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
            
            # vwap_value = (best_bid_price * best_bid_volume + best_ask_price * best_ask_volume) / (best_ask_volume + best_bid_volume)
            # self.kelp_vwap_cache.append(vwap_value)
            
            # if len(self.kelp_midprice_cache) > midprice_cache_size:
            #     self.kelp_midprice_cache.pop(0)
            # if len(self.kelp_vwap_cache) > vwap_cache_size:
            #     self.kelp_vwap_cache.pop(0)

            # fair_value = filtered_midprice

            fair_value = self.calculate_kelp_price(orderbook, state.timestamp)
            
            if best_ask_price <= fair_value - take_width:
                if best_ask_volume <= 20:
                    buy_quantity = min(best_ask_volume, POSITION_LIMITS[KELP] - position)
                    if buy_quantity > 0:
                        orders.append(Order(KELP, best_ask_price, buy_quantity))
                        total_buy_volume += buy_quantity
            
            if best_bid_price >= fair_value + take_width:
                if best_bid_volume  <= 20:
                    sell_quantity = min(best_bid_volume,POSITION_LIMITS[KELP] + position)
                    if sell_quantity > 0:
                        orders.append(Order(KELP, best_bid_price, sell_quantity))
                        total_sell_volume += sell_quantity
            
            total_buy_volume, total_sell_volume = self.clear_position_order(
                orders,
                orderbook,
                position,
                POSITION_LIMITS[KELP],
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
            
            remaining_buy_capacity = POSITION_LIMITS[KELP] - (position + total_buy_volume)
            if remaining_buy_capacity > 0:
                orders.append(Order(KELP, passive_buy_price + 1, remaining_buy_capacity))
            
            remaining_sell_capacity = POSITION_LIMITS[KELP] + (position - total_sell_volume)
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
                case "SQUID_INK":
                    result[SQUID_INK] = self.squid_try(state)
        
        return result, conversions, traderData