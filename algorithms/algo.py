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


BASKET1_WEIGHTS = {
    DJEMBES: 1,
    CROISSANTS: 6,
    JAMS: 3,
}

BASKET2_WEIGHTS = {
    CROISSANTS: 4,
    JAMS: 2,
}

SYNTH_WEIGHT = 0.05


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
    
    def get_orderbook_stats(self, orderbook: OrderDepth):
        mm_bids = {}
        mm_asks = {}
        best_ask_price = float('inf')
        best_ask_quantity = None
        best_bid_price = 0
        best_bid_quantity = None
        
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
            if abs(ask_quantity) >= 20:
                mm_asks[ask_price] = ask_quantity
        
        if len(mm_asks.keys()) == 0 or len(mm_bids.keys()) == 0:
            mm_best_ask = -1
            mm_best_bid = -1
            mm_midprice = -1
            mm_vwap = -1
        else:
            mm_best_ask = min(mm_asks.keys())
            mm_best_bid = max(mm_bids.keys())
            mm_midprice = (mm_best_ask + mm_best_bid) / 2
            mm_vwap = (mm_best_ask * mm_asks[mm_best_ask] + mm_best_bid * mm_bids[mm_best_bid])
        
        midprice = (best_ask_price + best_bid_price) / 2
        
        if best_ask_quantity + best_bid_quantity != 0:
            vwap = (best_ask_price * best_ask_quantity + best_bid_price * best_bid_quantity) / \
                (best_ask_quantity + best_bid_quantity)
        else:
            vwap = -1
        
        stats = {
            "mp": midprice,
            "vwap": vwap,
            "bb": best_bid_price,
            "ba": best_ask_price,
            "mm_mp": mm_midprice,
            "mm_vwap": mm_vwap,
            "mm_bb": mm_best_bid,
            "mm_ba": mm_best_ask
        }

        return stats
    
    
    def basket1_strategy(self, state: TradingState) -> List[Order]:
        orders: List[Order] = []
        orderbook = state.order_depths.get(PCB1)
        
        if not orderbook:
            return orders

        position = state.position.get(PCB1, 0)

        djembes_ob = state.order_depths.get(DJEMBES)
        croissants_ob = state.order_depths.get(CROISSANTS)
        jams_ob = state.order_depths.get(JAMS)

        basket_stats = self.get_orderbook_stats(orderbook)
        djembes_stats = self.get_orderbook_stats(djembes_ob)
        croissants_stats = self.get_orderbook_stats(croissants_ob)
        jams_stats = self.get_orderbook_stats(jams_ob)
        
        basket_mp = basket_stats["mp"]
        djembes_mp = djembes_stats["mp"]
        croissants_mp = croissants_stats["mp"]
        jams_mp = jams_stats["mp"]
        
        basket_theo = basket_mp
        
        synthetic_value = djembes_mp * BASKET1_WEIGHTS[DJEMBES] + \
            croissants_mp * BASKET1_WEIGHTS[CROISSANTS] + \
            jams_mp * BASKET1_WEIGHTS[JAMS]

        fair_value = (1 - SYNTH_WEIGHT) * basket_theo + SYNTH_WEIGHT * synthetic_value

        total_buy_volume = 0
        total_sell_volume = 0

        # Determine price levels for resting
        filtered_sell_orders = [price for price in orderbook.sell_orders.keys() if price > fair_value + 1]
        filtered_buy_orders = [price for price in orderbook.buy_orders.keys() if price < fair_value - 1]
        
        if not filtered_sell_orders or not filtered_buy_orders:
            return orders

        lowest_sell_above = min(filtered_sell_orders)
        highest_buy_below = max(filtered_buy_orders)

        # Buy if the best ask is below fair value
        if orderbook.sell_orders:
            best_ask_price = min(orderbook.sell_orders.keys())
            best_ask_volume = -orderbook.sell_orders[best_ask_price]
            if best_ask_price < fair_value:
                buy_quantity = min(best_ask_volume, POSITION_LIMITS[PCB1] - position)
                if buy_quantity > 0:
                    orders.append(Order(PCB1, best_ask_price, buy_quantity))
                    total_buy_volume += buy_quantity

        # Sell if the best bid is above fair value
        if orderbook.buy_orders:
            best_bid_price = max(orderbook.buy_orders.keys())
            best_bid_volume = orderbook.buy_orders[best_bid_price]
            if best_bid_price > fair_value:
                sell_quantity = min(best_bid_volume, POSITION_LIMITS[PCB1] + position)
                if sell_quantity > 0:
                    orders.append(Order(PCB1, best_bid_price, -sell_quantity))
                    total_sell_volume += sell_quantity

        # Clear net positions
        total_buy_volume, total_sell_volume = self.clear_position_order(
            orders,
            orderbook,
            position,
            POSITION_LIMITS[PCB1],
            PCB1,
            total_buy_volume,
            total_sell_volume,
            fair_value,
        )

        # Place additional resting orders
        remaining_buy_capacity = POSITION_LIMITS[PCB1] - (position + total_buy_volume)
        if remaining_buy_capacity > 0:
            orders.append(Order(PCB1, highest_buy_below + 1, remaining_buy_capacity))
        remaining_sell_capacity = POSITION_LIMITS[PCB1] + (position - total_sell_volume)
        if remaining_sell_capacity > 0:
            orders.append(Order(PCB1, lowest_sell_above - 1, -remaining_sell_capacity))

        return orders
    
    
    def basket2_strategy(self, state: TradingState) -> List[Order]:
        orders: List[Order] = []
        orderbook = state.order_depths.get(PCB2)
        
        if not orderbook:
            return orders

        position = state.position.get(PCB2, 0)

        croissants_ob = state.order_depths.get(CROISSANTS)
        jams_ob = state.order_depths.get(JAMS)

        basket_stats = self.get_orderbook_stats(orderbook)
        croissants_stats = self.get_orderbook_stats(croissants_ob)
        jams_stats = self.get_orderbook_stats(jams_ob)

        basket_mp = basket_stats["mp"]
        croissants_mp = croissants_stats["mp"]
        jams_mp = jams_stats["mp"]

        basket_theo = basket_mp

        synthetic_value = croissants_mp * BASKET2_WEIGHTS[CROISSANTS] + \
                        jams_mp * BASKET2_WEIGHTS[JAMS]

        fair_value = (1 - SYNTH_WEIGHT) * basket_theo + SYNTH_WEIGHT * synthetic_value

        total_buy_volume = 0
        total_sell_volume = 0

        filtered_sell_orders = [price for price in orderbook.sell_orders.keys() if price > fair_value + 1]
        filtered_buy_orders = [price for price in orderbook.buy_orders.keys() if price < fair_value - 1]

        if not filtered_sell_orders or not filtered_buy_orders:
            return orders

        lowest_sell_above = min(filtered_sell_orders)
        highest_buy_below = max(filtered_buy_orders)

        # Buy if the best ask is below fair value
        if orderbook.sell_orders:
            best_ask_price = min(orderbook.sell_orders.keys())
            best_ask_volume = -orderbook.sell_orders[best_ask_price]
            if best_ask_price < fair_value:
                buy_quantity = min(best_ask_volume, POSITION_LIMITS[PCB2] - position)
                if buy_quantity > 0:
                    orders.append(Order(PCB2, best_ask_price, buy_quantity))
                    total_buy_volume += buy_quantity

        # Sell if the best bid is above fair value
        if orderbook.buy_orders:
            best_bid_price = max(orderbook.buy_orders.keys())
            best_bid_volume = orderbook.buy_orders[best_bid_price]
            if best_bid_price > fair_value:
                sell_quantity = min(best_bid_volume, POSITION_LIMITS[PCB2] + position)
                if sell_quantity > 0:
                    orders.append(Order(PCB2, best_bid_price, -sell_quantity))
                    total_sell_volume += sell_quantity

        total_buy_volume, total_sell_volume = self.clear_position_order(
            orders,
            orderbook,
            position,
            POSITION_LIMITS[PCB2],
            PCB2,
            total_buy_volume,
            total_sell_volume,
            fair_value,
        )

        remaining_buy_capacity = POSITION_LIMITS[PCB2] - (position + total_buy_volume)
        if remaining_buy_capacity > 0:
            orders.append(Order(PCB2, highest_buy_below + 1, remaining_buy_capacity))

        remaining_sell_capacity = POSITION_LIMITS[PCB2] + (position - total_sell_volume)
        if remaining_sell_capacity > 0:
            orders.append(Order(PCB2, lowest_sell_above - 1, -remaining_sell_capacity))

        return orders
    

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
    
    
    
    def kelp_strategy(self, state: TradingState) -> List[Order]:
        orders: List[Order] = []

        # Load persistent trader data using JSON (if available).
        trader_data = {}
        if state.traderData:
            try:
                trader_data = json.loads(state.traderData)
            except Exception:
                trader_data = {}

        # Get the order depth for KELP; exit early if not available.
        kelp_order_depth = state.order_depths.get(KELP)
        if not kelp_order_depth:
            return orders

        kelp_position = state.position.get(KELP, 0)

        # Strategy parameters.
        take_width = 1
        clear_width = 0
        prevent_adverse = True
        adverse_volume = 20  # threshold volume to avoid adverse selection
        reversion_beta = -0.48903092360275835
        disregard_edge = 1
        join_edge = 0
        default_edge = 1
        position_limit = POSITION_LIMITS[KELP]

        ########################
        # 1. FAIR VALUE CALC
        ########################
        if kelp_order_depth.sell_orders and kelp_order_depth.buy_orders:
            best_ask = min(kelp_order_depth.sell_orders.keys())
            best_bid = max(kelp_order_depth.buy_orders.keys())

            # Filter orders to avoid those with small volumes.
            filtered_ask = [
                price for price, volume in kelp_order_depth.sell_orders.items()
                if abs(volume) >= adverse_volume
            ]
            filtered_bid = [
                price for price, volume in kelp_order_depth.buy_orders.items()
                if abs(volume) >= adverse_volume
            ]
            mm_ask = min(filtered_ask) if filtered_ask else None
            mm_bid = max(filtered_bid) if filtered_bid else None

            if mm_ask is None or mm_bid is None:
                # Use the previous mid price if available; otherwise, compute a new one.
                mid_price = trader_data.get("kelp_last_price", (best_ask + best_bid) / 2)
            else:
                mid_price = (mm_ask + mm_bid) / 2

            # Adjust fair value using mean reversion if we have a previous price.
            if "kelp_last_price" in trader_data:
                last_price = trader_data["kelp_last_price"]
                last_returns = (mid_price - last_price) / last_price
                pred_returns = last_returns * reversion_beta
                fair_value = mid_price + (mid_price * pred_returns)
            else:
                fair_value = mid_price

            trader_data["kelp_last_price"] = mid_price
        else:
            # Incomplete order book data, so no orders will be generated.
            return orders
        
        ########################
        # 2. TAKE ORDERS STEP
        ########################

        buy_order_volume = 0
        sell_order_volume = 0

        # On the sell side: if best ask is favorable, submit a buy order.
        if kelp_order_depth.sell_orders:
            best_ask = min(kelp_order_depth.sell_orders.keys())
            best_ask_volume = -kelp_order_depth.sell_orders[best_ask]
            if (not prevent_adverse or abs(best_ask_volume) <= adverse_volume) and \
               best_ask <= fair_value - take_width:
                quantity = min(best_ask_volume, position_limit - kelp_position)
                if quantity > 0:
                    orders.append(Order(KELP, best_ask, quantity))
                    buy_order_volume += quantity

        # On the buy side: if best bid is favorable, submit a sell order.
        if kelp_order_depth.buy_orders:
            best_bid = max(kelp_order_depth.buy_orders.keys())
            best_bid_volume = kelp_order_depth.buy_orders[best_bid]
            if (not prevent_adverse or abs(best_bid_volume) <= adverse_volume) and \
               best_bid >= fair_value + take_width:
                quantity = min(best_bid_volume, position_limit + kelp_position)
                if quantity > 0:
                    orders.append(Order(KELP, best_bid, -quantity))
                    sell_order_volume += quantity

        ########################
        # 3. CLEAR ORDERS STEP
        ########################
        
        position_after_take = kelp_position + buy_order_volume - sell_order_volume
        fair_bid = round(fair_value - clear_width)
        fair_ask = round(fair_value + clear_width)
        buy_capacity = position_limit - (kelp_position + buy_order_volume)
        sell_capacity = position_limit + (kelp_position - sell_order_volume)

        if position_after_take > 0:
            clear_quantity = sum(
                volume for price, volume in kelp_order_depth.buy_orders.items()
                if price >= fair_ask
            )
            clear_quantity = min(clear_quantity, position_after_take)
            sent_quantity = min(sell_capacity, clear_quantity)
            if sent_quantity > 0:
                orders.append(Order(KELP, fair_ask, -abs(sent_quantity)))
                sell_order_volume += abs(sent_quantity)
        elif position_after_take < 0:
            clear_quantity = sum(
                abs(volume) for price, volume in kelp_order_depth.sell_orders.items()
                if price <= fair_bid
            )
            clear_quantity = min(clear_quantity, abs(position_after_take))
            sent_quantity = min(buy_capacity, clear_quantity)
            if sent_quantity > 0:
                orders.append(Order(KELP, fair_bid, abs(sent_quantity)))
                buy_order_volume += abs(sent_quantity)

        ########################
        # 4. MARKET MAKING STEP
        ########################
        
        # Determine orders to join based on their distance from fair value.
        asks_above_fair = [
            price for price in kelp_order_depth.sell_orders.keys()
            if price > fair_value + disregard_edge
        ]
        bids_below_fair = [
            price for price in kelp_order_depth.buy_orders.keys()
            if price < fair_value - disregard_edge
        ]

        best_ask_above_fair = min(asks_above_fair) if asks_above_fair else None
        best_bid_below_fair = max(bids_below_fair) if bids_below_fair else None

        if best_ask_above_fair is not None:
            ask_price = best_ask_above_fair if abs(best_ask_above_fair - fair_value) <= join_edge \
                        else best_ask_above_fair - 1
        else:
            ask_price = round(fair_value + default_edge)

        if best_bid_below_fair is not None:
            bid_price = best_bid_below_fair if abs(fair_value - best_bid_below_fair) <= join_edge \
                        else best_bid_below_fair + 1
        else:
            bid_price = round(fair_value - default_edge)

        mm_buy_qty = position_limit - (kelp_position + buy_order_volume)
        if mm_buy_qty > 0:
            orders.append(Order(KELP, round(bid_price), mm_buy_qty))
        mm_sell_qty = position_limit + (kelp_position - sell_order_volume)
        if mm_sell_qty > 0:
            orders.append(Order(KELP, round(ask_price), -mm_sell_qty))

        # Store persistent data for subsequent rounds using JSON.
        state.traderData = json.dumps(trader_data)
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
                    result[KELP] = self.kelp_strategy(state)
                case "RAINFOREST_RESIN":
                    result[RESIN] = self.resin_strategy(state)
                case "SQUID_INK":
                    result[SQUID_INK] = self.squid_try(state)
                case "PICNIC_BASKET1":
                    result[PCB1] = self.basket1_strategy(state)
                case "PICNIC_BASKET2":
                    result[PCB2] = self.basket2_strategy(state)

        return result, conversions, traderData