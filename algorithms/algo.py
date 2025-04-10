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
        self.squid_midprice_cache = []
        self.squid_vwap_cache = []
        self.squid_mm_midprice_cache = []
        self.squid_mm_vwap_cache = []
    
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
        
        fair_price = None
        
        return orders

    
    def linear_clamp(self, x, a, b):
        """ Naive linear clamp """
        if x > b:
            return b
        elif x < a:
            return a
        return x
    
    
    def sigmoid_clamp(self, x, a, b):
        """ Shifted sigmoid clamp """
        val = 4 / a / (1 + math.exp(-a * (x - b))) - 2 / a + b
        return val
    
    def get_squid_ink_fair_price(self):
        pass
   
    def squid_ewa(self, state: TradingState, alpha_short, alpha_long):
        pass
    
    def squid_sma_strategy(self, state: TradingState, short_window_size, long_window_size):
        orderbook = state.order_depths.get(KELP)
        position = state.position.get(KELP, 0)
        orders: List[Order] = []
        total_buy_volume = 0
        total_sell_volume = 0
        
        # Fair price is determined by any quote with size >= 20
        if orderbook.sell_orders and orderbook.buy_orders:
            best_ask_price = min(orderbook.sell_orders.keys())
            best_bid_price = max(orderbook.buy_orders.keys())
            best_ask_volume = -orderbook.sell_orders[best_ask_price]
            best_bid_volume = orderbook.buy_orders[best_bid_price]
            
            midprice = (best_ask_price + best_bid_price) / 2
            vwap = (best_ask_price * best_ask_volume + best_bid_price * best_bid_volume) // (best_ask_volume + best_bid_volume)
            
            best_bid_price = 0
            best_ask_price = float('inf')
            
            best_bid_quantity = None
            best_ask_quantity = None
            
            market_maker_bids = {}
            market_maker_asks = {}
            
            # best_bid_price, best_bid_quantity, market maker orderbook
            for bid_price, bid_quantity in orderbook.buy_orders.items():
                if bid_price > best_bid_price:
                    best_bid_price = bid_price
                    best_bid_quantity = bid_quantity
                if bid_quantity >= 20:
                    market_maker_bids[bid_price] = bid_quantity
            
            # best_ask_price, best_ask_quantity, market maker orderbook
            for ask_price, ask_quantity in orderbook.sell_orders.items():
                if ask_price < best_ask_price:
                    best_ask_price = ask_price
                    best_ask_quantity = ask_quantity
                if ask_quantity >= 20:
                    market_maker_asks[ask_price] = ask_quantity
            
            mm_best_bid_price = min(market_maker_bids.keys())
            mm_best_bid_quantity = market_maker_bids[mm_best_bid_price]
            mm_best_ask_price = max(market_maker_asks.keys())
            mm_best_ask_quantity = market_maker_asks[mm_best_ask_price]
        
            mm_midprice = (mm_best_bid_price + mm_best_ask_price) // 2
            mm_vwap = (mm_best_bid_price * mm_best_bid_quantity + mm_best_ask_price * mm_best_ask_quantity)\
                // (mm_best_bid_quantity + mm_best_ask_quantity)
        
            self.squid_midprice_cache.append(midprice)
            self.squid_vwap_cache.append(vwap)
            self.squid_mm_midprice_cache.append(mm_midprice)
            self.squid_mm_vwap_cache.append(mm_vwap)

            
            
        return orders
    
    
    def squid_sma(self, state: TradingState, short_window_size: int, long_window_size: int) -> List[Order]:
        # Get the SQUID_INK order book and current position.
        orderbook = state.order_depths.get(SQUID_INK)
        position = state.position.get(SQUID_INK, 0)
        orders: List[Order] = []
        
        # Check that the order book is valid.
        if orderbook is None or not orderbook.buy_orders or not orderbook.sell_orders:
            return orders
        
        # Compute the best bid and best ask prices.
        best_ask = min(orderbook.sell_orders.keys())
        best_bid = max(orderbook.buy_orders.keys())
        # Midprice is the average of best ask and best bid.
        midprice = (best_ask + best_bid) / 2

        # Update the price cache.
        self.squid_midprice_cache.append(midprice)
        # Optionally, limit the cache length to avoid unbounded growth.
        if len(self.squid_midprice_cache) > long_window_size:
            self.squid_midprice_cache.pop(0)
        else:
            return []

        # Compute the simple moving averages:
        # Use all available prices if fewer than the window size.
        recent_short = self.squid_midprice_cache[-short_window_size:] if len(self.squid_midprice_cache) >= short_window_size else self.squid_midprice_cache
        recent_long  = self.squid_midprice_cache[-long_window_size:] if len(self.squid_midprice_cache) >= long_window_size else self.squid_midprice_cache

        short_sma = sum(recent_short) / len(recent_short)
        long_sma  = sum(recent_long)  / len(recent_long)

        # Determine the target position:
        # If the short-term SMA is above the long-term SMA, go all in long.
        # Otherwise, go all in short.
        if short_sma > long_sma:
            target_position = POS_LIMIT_SQUID_INK  # fully long
        else:
            target_position = -POS_LIMIT_SQUID_INK  # fully short

        # Calculate the order quantity required to adjust the position.
        order_quantity = target_position - position

        if order_quantity != 0:
            # If buying, execute at the best ask price.
            if order_quantity > 0:
                orders.append(Order(SQUID_INK, best_ask, order_quantity))
            # If selling, execute at the best bid price.
            else:
                orders.append(Order(SQUID_INK, best_bid, order_quantity))
        
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
                    result[SQUID_INK] = self.squid_sma(state, 10, 50)
                case _:
                    pass
        
        return result, conversions, traderData