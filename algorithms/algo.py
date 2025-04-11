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
        self.ema_diff_history = []

    def squid_ema(self, state: TradingState, short_alpha: float, long_alpha: float, threshold) -> List[Order]:        
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
        
        if state.timestamp < 500:
            return [], ""
        
        orderbook = state.order_depths.get(SQUID_INK)
        position = state.position.get(SQUID_INK, 0)
        orders: List[Order] = []
        
        # Validate that the order book has data.
        if orderbook is None or not orderbook.buy_orders or not orderbook.sell_orders:
            return orders, ""
        
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
        
        mm_best_bid, mm_best_ask = None, None
        
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
        
        if self.ema_short == 0.0 or self.ema_long == 0.0:
            return [], ""
        
        # print(self.ema_short - self.ema_long)
        # print("---", fair_price)
        
        # Compute the current EMA difference.
        current_diff = self.ema_short - self.ema_long
        
        # If the previous EMA difference is not available yet, store and exit.
        if self.prev_ema_diff is None:
            self.prev_ema_diff = current_diff
            return orders, ""
        
        # Initialize variables for crossover detection.
        crossover_detected = False
        target_position = 0
        
        # Bullish crossover: previous diff ≤ 0 and current diff > 0.
        if self.prev_ema_diff < -threshold and current_diff > threshold:
            crossover_detected = True
            target_position = POS_LIMIT_SQUID_INK
        
        # Bearish crossover: previous diff ≥ 0 and current diff < 0.
        elif self.prev_ema_diff > threshold and current_diff < -threshold:
            crossover_detected = True
            target_position = -POS_LIMIT_SQUID_INK
        
        # if crossover_detected:
        #     print(f"Crossover detected! Prev difference is {self.prev_ema_diff} and current is {current_diff}")
        
        # Update the stored EMA difference.
        self.prev_ema_diff = current_diff
        
        trader_data = None
        
        # If a crossover is detected, determine the order quantity required.
        if crossover_detected:
            order_quantity = target_position - position
            if order_quantity != 0:
                if order_quantity > 0: # buy
                    remaining_quantity = order_quantity
                    trader_data = "+"
                    if mm_best_ask:
                        orders.append(Order(SQUID_INK, mm_best_ask, order_quantity))
                    else:
                        orders.append(Order(SQUID_INK, best_ask_price, order_quantity))
                else: # sell
                    trader_data = "-"
                    if mm_best_bid:
                        orders.append(Order(SQUID_INK, mm_best_bid, order_quantity))
                    else:
                        orders.append(Order(SQUID_INK, best_bid_price, order_quantity))
        else:
            if state.traderData == "+":
                target_position = POS_LIMIT_SQUID_INK
            elif state.traderData == "-":
                target_position = -POS_LIMIT_SQUID_INK
            trader_data = ""
            order_quantity = target_position - position
            if order_quantity != 0:
                if order_quantity > 0: # buy
                    remaining_quantity = order_quantity
                    if mm_best_ask:
                        orders.append(Order(SQUID_INK, mm_best_ask, order_quantity))
                    else:
                        orders.append(Order(SQUID_INK, best_ask_price, order_quantity))
                else: # sell
                    if mm_best_bid:
                        orders.append(Order(SQUID_INK, mm_best_bid, order_quantity))
                    else:
                        orders.append(Order(SQUID_INK, best_bid_price, order_quantity))

        return orders, trader_data
    
    
    def advanced_squid_ema(self, state: TradingState, short_alpha: float, long_alpha: float, threshold) -> Tuple[List[Order], str]:
        """
        Predictive EMA crossover strategy for SQUID_INK:

        - Computes current midprice from the best ask and bid.
        - Updates short and long EMAs.
        - Calculates the difference and adds it to a history buffer.
        - Fits a simple linear regression over the last few differences (window = 3 by default)
          to project the next tick’s EMA difference.
        - If the predicted difference indicates that a crossover will occur soon (i.e. for a bullish
          case: current difference is below the threshold but the prediction is above; for bearish, vice versa),
          an order is placed immediately.
        - If prediction is not available (due to insufficient history), then the previous method’s crossover
          check is used.
        - Orders are executed at the best available price from the market-maker prices if available.
        """
        if state.timestamp < 500:
            return [], ""
        
        orderbook = state.order_depths.get(SQUID_INK)
        position = state.position.get(SQUID_INK, 0)
        orders: List[Order] = []
        
        # Validate that the order book has data.
        if orderbook is None or not orderbook.buy_orders or not orderbook.sell_orders:
            return orders, ""
        
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
        
        mm_best_bid, mm_best_ask = None, None
        
        if mm_asks and mm_bids:
            mm_best_bid = max(mm_bids.keys())
            mm_best_ask = min(mm_asks.keys())
            mm_midprice = (mm_best_ask + mm_best_bid) / 2
            mm_vwap = (mm_best_ask * mm_asks[mm_best_ask] + mm_best_bid * mm_bids[mm_best_bid])
            fair_price = mm_midprice
        else:
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
        
        # Guard against division issues.
        if self.ema_short == 0.0 or self.ema_long == 0.0:
            return [], ""
        
        # Compute the current EMA difference.
        current_diff = self.ema_short - self.ema_long
        
        # Append current difference to history and maintain a fixed window.
        self.ema_diff_history.append(current_diff)
        WINDOW_SIZE = 3
        if len(self.ema_diff_history) > WINDOW_SIZE:
            self.ema_diff_history.pop(0)
        
        # Set a flag for detecting a predicted crossover.
        crossover_detected = False
        target_position = 0
        trader_data = ""
        
        # --- Predictive Logic ---
        projected_signal = None
        if len(self.ema_diff_history) >= 2:
            # We'll use the indices 0, 1, ..., (n-1) as our independent variable.
            n = len(self.ema_diff_history)
            x = list(range(n))
            y = self.ema_diff_history
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_xx = sum(x[i] * x[i] for i in range(n))
            denominator = n * sum_xx - (sum_x ** 2)
            slope = (n * sum_xy - sum_x * sum_y) / denominator if denominator != 0 else 0
            intercept = (sum_y - slope * sum_x) / n
            # Predict the difference at the next tick (using lookahead = 1 tick).
            projected_diff = slope * n + intercept

            # Debug (you can remove these prints in production):
            # print(f"Current diff: {current_diff}, Projected diff: {projected_diff}")

            # Bullish predicted crossover:
            if current_diff < threshold and projected_diff >= threshold:
                projected_signal = "bullish"
            # Bearish predicted crossover:
            elif current_diff > -threshold and projected_diff <= -threshold:
                projected_signal = "bearish"
        
        # If prediction was available, use it for determining orders.
        if projected_signal is not None:
            crossover_detected = True
            if projected_signal == "bullish":
                target_position = POS_LIMIT_SQUID_INK
                trader_data = "+"
            elif projected_signal == "bearish":
                target_position = -POS_LIMIT_SQUID_INK
                trader_data = "-"
        else:
            # --- Fallback to original crossover detection ---
            if self.prev_ema_diff is None:
                self.prev_ema_diff = current_diff
            if self.prev_ema_diff < -threshold and current_diff > threshold:
                crossover_detected = True
                target_position = POS_LIMIT_SQUID_INK
                trader_data = "+"
            elif self.prev_ema_diff > threshold and current_diff < -threshold:
                crossover_detected = True
                target_position = -POS_LIMIT_SQUID_INK
                trader_data = "-"
        
        # Update stored EMA difference.
        self.prev_ema_diff = current_diff
        
        # If a crossover is detected, determine the order quantity and add order(s).
        if crossover_detected:
            order_quantity = target_position - position
            if order_quantity != 0:
                if order_quantity > 0:  # buy
                    if mm_best_ask:
                        orders.append(Order(SQUID_INK, mm_best_ask, order_quantity))
                    else:
                        orders.append(Order(SQUID_INK, best_ask_price, order_quantity))
                else:  # sell
                    if mm_best_bid:
                        orders.append(Order(SQUID_INK, mm_best_bid, order_quantity))
                    else:
                        orders.append(Order(SQUID_INK, best_bid_price, order_quantity))
        
        return orders, trader_data
    
    
    def squid_sma(self, state: TradingState, short_window_size: int, long_window_size: int) -> Tuple[List[Order], str]:
        """
        Enhanced SMA crossover strategy for SQUID_INK:
        
        - Uses market maker prices (if available) for order execution.
        - Computes the SMA from a rolling cache of midprices.
        - When a crossover is detected (SMA short crossing above or below SMA long), determines the
          total required order to reach the target position.
        - Instead of placing the full order at once, the order is sliced into smaller chunks to reduce
          market impact.
        """
        orders: List[Order] = []
        trader_data = ""
        
        orderbook = state.order_depths.get(SQUID_INK)
        position = state.position.get(SQUID_INK, 0)
        
        if orderbook is None or not orderbook.buy_orders or not orderbook.sell_orders:
            return orders, trader_data
        
        # Build order book info: best bid/ask and market-maker (mm) quotes.
        best_bid_price = 0
        best_bid_quantity = None
        best_ask_price = float('inf')
        best_ask_quantity = None
        
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
        
        mm_best_bid, mm_best_ask = None, None
        if mm_bids and mm_asks:
            mm_best_bid = max(mm_bids.keys())
            mm_best_ask = min(mm_asks.keys())
        else:
            mm_best_bid = best_bid_price
            mm_best_ask = best_ask_price
        
        # Compute the current midprice and update the SMA cache.
        midprice = (best_bid_price + best_ask_price) / 2
        mm_midprice = (mm_best_bid + mm_best_ask) / 2
        self.squid_midprice_cache.append(midprice)
        if len(self.squid_midprice_cache) > long_window_size:
            self.squid_midprice_cache.pop(0)
        else:
            # Not enough data yet for SMA; wait until we have a full long window.
            return orders, trader_data
        
        # Compute SMA signals.
        recent_short = self.squid_midprice_cache[-short_window_size:]
        recent_long  = self.squid_midprice_cache[-long_window_size:]
        short_sma = sum(recent_short) / len(recent_short)
        long_sma  = sum(recent_long) / len(recent_long)
        current_diff = short_sma - long_sma
        
        if self.prev_sma_diff is None:
            self.prev_sma_diff = current_diff
            return orders, trader_data
        
        crossover_detected = False
        target_position = 0
        
        # Detect crossovers.
        if self.prev_sma_diff <= 0 and current_diff > 0:
            crossover_detected = True
            target_position = POS_LIMIT_SQUID_INK
        elif self.prev_sma_diff >= 0 and current_diff < 0:
            crossover_detected = True
            target_position = -POS_LIMIT_SQUID_INK
        
        self.prev_sma_diff = current_diff
        
        print(self.ema_short - self.ema_long)
        print("---", midprice)
        
        # Only proceed when a crossover is detected.
        if not crossover_detected:
            return orders, trader_data
        
        # Determine the total order quantity needed.
        total_order_quantity = target_position - position
        
        # Slice the order to reduce market impact.
        # Here we choose a fixed slice size (for example, 10 units per tick).
        SLICE_SIZE = 10
        if abs(total_order_quantity) > SLICE_SIZE:
            order_quantity = SLICE_SIZE if total_order_quantity > 0 else -SLICE_SIZE
        else:
            order_quantity = total_order_quantity
        
        # Use market maker prices if available.
        if order_quantity > 0:
            trader_data = "+"
            price = mm_best_ask if mm_best_ask is not None else best_ask_price
            orders.append(Order(SQUID_INK, price, order_quantity))
        elif order_quantity < 0:
            trader_data = "-"
            price = mm_best_bid if mm_best_bid is not None else best_bid_price
            orders.append(Order(SQUID_INK, price, order_quantity))
        
        return orders, trader_data
    
    def squid_ema(self, state: TradingState, short_alpha: float, long_alpha: float, threshold) -> Tuple[List[Order], str]:
        """
        Predictive EMA crossover strategy for SQUID_INK with improved entry check:

          - Computes current midprice and updates short and long EMAs.
          - Adds the current EMA difference to a history buffer.
          - Fits a linear regression (over a small window) to project next-tick difference.
          - Signals a crossover if the projected value crosses the threshold.
          - **New:** Checks the execution price against the estimated fair price.
                   For buys, if the best ask is too high (more than fair_price*(1+margin)),
                   the order is skipped. Similarly for sells.
          - Orders are executed using market-maker prices if available.
        """
        if state.timestamp < 500:
            return [], ""
        
        orderbook = state.order_depths.get(SQUID_INK)
        position = state.position.get(SQUID_INK, 0)
        orders: List[Order] = []
        
        # Check for valid order book data.
        if orderbook is None or not orderbook.buy_orders or not orderbook.sell_orders:
            return orders, ""
        
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

        mm_best_bid, mm_best_ask = None, None

        if mm_asks and mm_bids:
            mm_best_bid = max(mm_bids.keys())
            mm_best_ask = min(mm_asks.keys())
            # Use market-maker midprice as fair price.
            mm_midprice = (mm_best_ask + mm_best_bid) / 2
            fair_price = mm_midprice
        else:
            midprice = (best_bid_price + best_ask_price) / 2
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

        if self.ema_short == 0.0 or self.ema_long == 0.0:
            return [], ""

        # Compute current EMA difference.
        current_diff = self.ema_short - self.ema_long

        # Update the history for the EMA difference.
        self.ema_diff_history.append(current_diff)
        WINDOW_SIZE = 3
        if len(self.ema_diff_history) > WINDOW_SIZE:
            self.ema_diff_history.pop(0)

        # Initialize variables for signal and target.
        crossover_detected = False
        target_position = 0
        trader_data = ""

        # --- Predictive Linear Regression ---
        projected_signal = None
        if len(self.ema_diff_history) >= 2:
            n = len(self.ema_diff_history)
            x = list(range(n))
            y = self.ema_diff_history
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_xx = sum(x[i] * x[i] for i in range(n))
            denominator = n * sum_xx - (sum_x ** 2)
            slope = (n * sum_xy - sum_x * sum_y) / denominator if denominator != 0 else 0
            intercept = (sum_y - slope * sum_x) / n
            # Predict next tick (lookahead = 1).
            projected_diff = slope * n + intercept

            # Determine predictive signal.
            if current_diff < threshold and projected_diff >= threshold:
                projected_signal = "bullish"
            elif current_diff > -threshold and projected_diff <= -threshold:
                projected_signal = "bearish"

        # Use prediction if available; else fallback to prior diff.
        if projected_signal is not None:
            crossover_detected = True
            if projected_signal == "bullish":
                target_position = POS_LIMIT_SQUID_INK
                trader_data = "+"
            elif projected_signal == "bearish":
                target_position = -POS_LIMIT_SQUID_INK
                trader_data = "-"
        else:
            if self.prev_ema_diff is None:
                self.prev_ema_diff = current_diff
            if self.prev_ema_diff < -threshold and current_diff > threshold:
                crossover_detected = True
                target_position = POS_LIMIT_SQUID_INK
                trader_data = "+"
            elif self.prev_ema_diff > threshold and current_diff < -threshold:
                crossover_detected = True
                target_position = -POS_LIMIT_SQUID_INK
                trader_data = "-"
        self.prev_ema_diff = current_diff

        # NEW: Add a price validation check to avoid buying at too high or selling at too low prices.
        # Define a margin percentage (this example uses 0.2%, adjust as needed).
        margin = 0.002

        if crossover_detected:
            if target_position > 0:  # Bullish: intent to buy.
                execution_price = mm_best_ask if mm_best_ask is not None else best_ask_price
                # Only buy if the price is within an acceptable range of fair_price.
                if execution_price > fair_price * (1 + margin):
                    crossover_detected = False
            elif target_position < 0:  # Bearish: intent to sell.
                execution_price = mm_best_bid if mm_best_bid is not None else best_bid_price
                # Only sell if the price is within an acceptable range of fair_price.
                if execution_price < fair_price * (1 - margin):
                    crossover_detected = False

        # If, after validation, a crossover signal holds, execute the order.
        if crossover_detected:
            order_quantity = target_position - position
            if order_quantity != 0:
                if order_quantity > 0:  # Buy order.
                    if mm_best_ask:
                        orders.append(Order(SQUID_INK, mm_best_ask, order_quantity))
                    else:
                        orders.append(Order(SQUID_INK, best_ask_price, order_quantity))
                else:  # Sell order.
                    if mm_best_bid:
                        orders.append(Order(SQUID_INK, mm_best_bid, order_quantity))
                    else:
                        orders.append(Order(SQUID_INK, best_bid_price, order_quantity))

        return orders, trader_data


    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        """
        Process orders for all symbols.
        """
        result = {}
        traderData = "" 
        conversions = 1
        
        for product in state.order_depths:
            match product:
                case "SQUID_INK":
                    # Use a short window of 10 and a long window of 50 for example.
                    # squid_orders, traderData = self.advanced_squid_ema(state, 0.3, 0.1, 0.000)
                    squid_orders, traderData = self.squid_sma(state, 5, 10)
                    result[SQUID_INK] = squid_orders
                case _:
                    pass
        
        return result, conversions, traderData