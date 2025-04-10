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
        # New attribute for storing the previous SMA difference.
        self.prev_sma_diff = None
        # For EMA strategy: previous EMA values and difference.
        self.ema_short = None
        self.ema_long = None
        self.prev_ema_diff = None

    def squid_ema(self, state: TradingState, short_alpha: float, long_alpha: float) -> List[Order]:
        """
        EMA crossover strategy for SQUID_INK:
        
        - Computes current midprice from the best ask and bid.
        - Updates the short and long EMAs as:
              EMA_new = alpha * current_midprice + (1 - alpha) * EMA_old
          If no previous EMA exists, the current midprice is used to initialize the EMA.
        - The difference between the short and long EMA is computed.
        - A bullish crossover (previous difference ≤ 0 and current difference > 0)
          triggers an order to target a full long position (POS_LIMIT_SQUID_INK).
        - A bearish crossover (previous difference ≥ 0 and current difference < 0)
          triggers an order to target a full short position (-POS_LIMIT_SQUID_INK).
        - Orders are executed at the best available price:
              * Buy orders use the current best ask.
              * Sell orders use the current best bid.
        """
        orderbook = state.order_depths.get(SQUID_INK)
        position = state.position.get(SQUID_INK, 0)
        orders: List[Order] = []
        
        # Validate that the order book has data.
        if orderbook is None or not orderbook.buy_orders or not orderbook.sell_orders:
            return orders
        
        best_ask_price = float('inf')
        best_ask_quantity = None
        best_bid_price = 0
        best_bid_quantity = None
        
        mm_bids = {}
        mm_asks = {}
        
        for bid_price, bid_quantity in orderbook.buy_orders.items():
            if bid_price > best_bid_price:
                best_bid_price = bid_price
                best_bid_quantity = bid_quantity
            if bid_quantity >= 20:
                mm_bids[bid_price] = bid_quantity
        
        for ask_price, ask_quantity in orderbook.sell_orders.items():
            if ask_price < best_ask_price:
                best_ask_price = ask_price 
                best_ask_quantity = ask_quantity
            if -ask_quantity >= 20:
                mm_asks[ask_price] = ask_quantity
        
        # print("HI")
        # print(mm_asks)
        # print(mm_bids)
        
        if mm_asks and mm_bids:
            mm_best_ask = min(mm_asks.keys())
            mm_best_bid = max(mm_bids.keys())
            mm_midprice = (mm_best_ask + mm_best_bid) / 2
            mm_vwap = (mm_best_ask * mm_asks[mm_best_ask] + mm_best_bid * mm_bids[mm_best_bid])
            fair_price = mm_midprice
        else:
            # Determine the best available bid and ask
            
            # Compute the current midprice
            midprice = (best_bid_price + best_ask_price) / 2
            vwap = (best_ask_price * best_ask_quantity + best_bid_price * best_bid_quantity) \
                / (best_ask_quantity + best_bid_quantity)
            fair_price = midprice

        # Update (or initialize) the EMA values.
        if self.ema_short is None:
            self.ema_short = fair_price
        else:
            self.ema_short = short_alpha * fair_price + (1 - short_alpha) * self.ema_short
            
        if self.ema_long is None:
            self.ema_long = fair_price
        else:
            self.ema_long = long_alpha * fair_price + (1 - long_alpha) * self.ema_long
        
        # Compute the current EMA difference.
        current_diff = self.ema_short - self.ema_long
        
        # If the previous EMA difference is not available yet, store and exit.
        if self.prev_ema_diff is None:
            self.prev_ema_diff = current_diff
            return orders
        
        # Initialize variables for crossover detection.
        crossover_detected = False
        target_position = 0
        
        # Bullish crossover: previous diff ≤ 0 and current diff > 0.
        if self.prev_ema_diff <= 0 and current_diff > 0:
            crossover_detected = True
            target_position = POS_LIMIT_SQUID_INK
        
        # Bearish crossover: previous diff ≥ 0 and current diff < 0.
        elif self.prev_ema_diff >= 0 and current_diff < 0:
            crossover_detected = True
            target_position = -POS_LIMIT_SQUID_INK
        
        # Update the stored EMA difference.
        self.prev_ema_diff = current_diff
        
        # If a crossover is detected, determine the order quantity required.
        if crossover_detected:
            order_quantity = target_position - position
            if order_quantity != 0:
                # Buy if order_quantity > 0 (using best ask)
                if order_quantity > 0:
                    orders.append(Order(SQUID_INK, best_ask_price, order_quantity))
                else:
                    orders.append(Order(SQUID_INK, best_bid_price, order_quantity))
        
        return orders


    def squid_sma(self, state: TradingState, short_window_size: int, long_window_size: int) -> List[Order]:
        # Get the SQUID_INK order book and current position.
        orderbook = state.order_depths.get(SQUID_INK)
        position = state.position.get(SQUID_INK, 0)
        orders: List[Order] = []
        
        # Ensure order book data is valid.
        if orderbook is None or not orderbook.buy_orders or not orderbook.sell_orders:
            return orders
        
        # Determine the best bid and ask prices.
        best_ask = min(orderbook.sell_orders.keys())
        best_bid = max(orderbook.buy_orders.keys())
        # Compute the midprice.
        midprice = (best_ask + best_bid) / 2

        # Update the price cache.
        self.squid_midprice_cache.append(midprice)
        # Limit the cache length to avoid unbounded growth.
        if len(self.squid_midprice_cache) > long_window_size:
            self.squid_midprice_cache.pop(0)
        else:
            # If there are not enough cached values, don't issue any orders.
            return []

        # Compute the simple moving averages.
        recent_short = self.squid_midprice_cache[-short_window_size:] if len(self.squid_midprice_cache) >= short_window_size else self.squid_midprice_cache
        recent_long  = self.squid_midprice_cache[-long_window_size:] if len(self.squid_midprice_cache) >= long_window_size else self.squid_midprice_cache

        short_sma = sum(recent_short) / len(recent_short)
        long_sma  = sum(recent_long)  / len(recent_long)

        # Calculate the difference between the SMAs.
        current_diff = short_sma - long_sma

        # If we don't have a previous difference yet, initialize it and wait for the next tick.
        if self.prev_sma_diff is None:
            self.prev_sma_diff = current_diff
            return orders

        # Check for a crossover:
        # Bullish crossover: previous diff ≤ 0 and current diff > 0.
        # Bearish crossover: previous diff ≥ 0 and current diff < 0.
        crossover_detected = False
        target_position = 0

        if self.prev_sma_diff <= 0 and current_diff > 0:
            # Upward crossover detected: target fully long.
            crossover_detected = True
            target_position = POS_LIMIT_SQUID_INK
        elif self.prev_sma_diff >= 0 and current_diff < 0:
            # Downward crossover detected: target fully short.
            crossover_detected = True
            target_position = -POS_LIMIT_SQUID_INK

        # Update the stored difference for next time.
        self.prev_sma_diff = current_diff

        # If no crossover event is detected, do not issue any new orders.
        if not crossover_detected:
            return orders

        # Calculate the order quantity required to adjust the current position.
        order_quantity = target_position - position

        if order_quantity != 0:
            # Place the order at the appropriate side of the market:
            if order_quantity > 0:
                orders.append(Order(SQUID_INK, best_ask, order_quantity))
            else:
                orders.append(Order(SQUID_INK, best_bid, order_quantity))
        
        return orders

    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        """
        Process orders for all symbols.
        """
        result = {}
        traderData = "SAMPLE" 
        conversions = 1
        
        for product in state.order_depths:
            match product:
                case "SQUID_INK":
                    # Use a short window of 10 and a long window of 50 for example.
                    result[SQUID_INK] = self.squid_ema(state, 0.3, 0.15)
                case _:
                    pass
        
        return result, conversions, traderData