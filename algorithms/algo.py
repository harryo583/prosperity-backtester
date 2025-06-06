from typing import Dict, List, Tuple
from datamodel import OrderDepth, TradingState, Order
import json
import math 
import jsonpickle
import numpy as np
from statistics import NormalDist

PRODUCTS = ["RAINFOREST_RESIN", "KELP", "SQUID_INK", "CROISSANTS", "DJEMBES", "JAMS", "PICNIC_BASKET1", "PICNIC_BASKET2"]

RESIN = "RAINFOREST_RESIN"
KELP = "KELP"
SQUID_INK = "SQUID_INK"
CROISSANTS = "CROISSANTS"
DJEMBES = "DJEMBES"
JAMS = "JAMS"
PCB1 = "PICNIC_BASKET1"
PCB2 = "PICNIC_BASKET2"

VOLCANIC_ROCK = "VOLCANIC_ROCK"
VOLCANIC_ROCK_VOUCHER_9500 = "VOLCANIC_ROCK_VOUCHER_9500"
VOLCANIC_ROCK_VOUCHER_9750 = "VOLCANIC_ROCK_VOUCHER_9750"
VOLCANIC_ROCK_VOUCHER_10000 = "VOLCANIC_ROCK_VOUCHER_10000"
VOLCANIC_ROCK_VOUCHER_10250 = "VOLCANIC_ROCK_VOUCHER_10250"
VOLCANIC_ROCK_VOUCHER_10500 = "VOLCANIC_ROCK_VOUCHER_10500"


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
    PCB2: 100,
    VOLCANIC_ROCK: 400,
    VOLCANIC_ROCK_VOUCHER_9500: 200,
    VOLCANIC_ROCK_VOUCHER_9750: 200,
    VOLCANIC_ROCK_VOUCHER_10000: 200,
    VOLCANIC_ROCK_VOUCHER_10250: 200,
    VOLCANIC_ROCK_VOUCHER_10500: 200
}

BUY = "BUY"
SELL = "SELL"

THRESHOLD_LOW = -2.0
THRESHOLD_HIGH = 2.0
WINDOW_SIZE = 50
SQUID_POSITION_LIMIT = 50

TIME_TO_EXPIRY = 248/252

VOLCANIC_PARAMS = {
    VOLCANIC_ROCK_VOUCHER_9500: {
        "ivolatility": 0.16,
        "delta": 0.5,
        "gamma": 0.1,
        "target_position": 0,
        "join_edge": 5,
        "disregard_edge": 0,
        "default_edge": 0,
        "take_width": 1,
        "strike": 9500
    },
    VOLCANIC_ROCK_VOUCHER_9750: {
        "ivolatility": 0.16,
        "delta": 0.5,
        "gamma": 0.1,
        "target_position": 0,
        "join_edge": 3,
        "disregard_edge": 0,
        "default_edge": 0,
        "take_width": 1,
        "strike": 9750
    },
    VOLCANIC_ROCK_VOUCHER_10000: {
        "ivolatility": 0.16,
        "delta": 0.5,
        "gamma": 0.1,
        "target_position": 0,
        "join_edge": 3,
        "disregard_edge": 0.5,
        "default_edge": 4,
        "take_width": 0.5,
        "strike": 10000
    },
    VOLCANIC_ROCK_VOUCHER_10250: {
        "ivolatility": 0.16,
        "delta": 0.5,
        "gamma": 0.1,
        "target_position": 0,
        "join_edge": 1.5,
        "disregard_edge": 1,
        "default_edge": 4,
        "take_width": 0.5,
        "strike": 10250
    },
    VOLCANIC_ROCK_VOUCHER_10500: {
        "ivolatility": 0.2,
        "delta": 0.5,
        "gamma": 0.1,
        "target_position": 0,
        "join_edge": 1.5,
        "disregard_edge": 1,
        "default_edge": 4,
        "take_width": 1,
        "strike": 10500
    },
}
VOLCANIC_VOUCHERS = [
    VOLCANIC_ROCK_VOUCHER_9500,
    VOLCANIC_ROCK_VOUCHER_9750,
    VOLCANIC_ROCK_VOUCHER_10000,
    VOLCANIC_ROCK_VOUCHER_10250,
    VOLCANIC_ROCK_VOUCHER_10500
]

class BlackScholesGreeks:
    @staticmethod
    def _compute_shared(spot, strike, T, vol, r=0.0, q=0.0):
        """Precompute shared values for Greeks and price"""
        sqrt_T = math.sqrt(T)
        log_SK = math.log(spot / strike)
        drift_adj = (r - q + 0.5 * vol**2) * T
        
        d1 = (log_SK + drift_adj) / (vol * sqrt_T)
        d2 = d1 - vol * sqrt_T
        
        pdf_d1 = NormalDist().pdf(d1)
        cdf_d1 = NormalDist().cdf(d1)
        cdf_d2 = NormalDist().cdf(d2)
        
        return {
            'd1': d1,
            'd2': d2,
            'pdf_d1': pdf_d1,
            'cdf_d1': cdf_d1,
            'cdf_d2': cdf_d2,
            'sqrt_T': sqrt_T,
            'discount': math.exp(-r * T),
            'div_discount': math.exp(-q * T)
        }

    @staticmethod
    def call_price(spot, strike, T, vol, r=0.0, q=0.0):
        shared = BlackScholesGreeks._compute_shared(spot, strike, T, vol, r, q)
        return (spot * shared['div_discount'] * shared['cdf_d1'] 
                - strike * shared['discount'] * shared['cdf_d2'])

    @staticmethod
    def delta(spot, strike, T, vol, r=0.0, q=0.0):
        shared = BlackScholesGreeks._compute_shared(spot, strike, T, vol, r, q)
        return shared['div_discount'] * shared['cdf_d1']

    @staticmethod
    def gamma(spot, strike, T, vol, r=0.0, q=0.0):
        shared = BlackScholesGreeks._compute_shared(spot, strike, T, vol, r, q)
        return (shared['div_discount'] * shared['pdf_d1'] 
                / (spot * vol * shared['sqrt_T']))

    @staticmethod
    def vega(spot, strike, T, vol, r=0.0, q=0.0):
        shared = BlackScholesGreeks._compute_shared(spot, strike, T, vol, r, q)
        return spot * shared['div_discount'] * math.sqrt(T) * shared['pdf_d1']

    @staticmethod
    def implied_volatility_newton(market_price, spot, strike, T, r=0.0, q=0.0):
        """Newton-Raphson with analytical vega and value reuse"""
        def f(sigma):
            # Reuse all precomputed values for Greeks
            
            shared = BlackScholesGreeks._compute_shared(spot, strike, T, sigma, r, q)
            price = (spot * shared['div_discount'] * shared['cdf_d1'] 
                     - strike * shared['discount'] * shared['cdf_d2'])
            vega = spot * shared['div_discount'] * shared['sqrt_T'] * shared['pdf_d1']
            return price - market_price, vega

        try:
            # Use Newton with analytical derivative
            return newton(
                func=lambda x: f(x)[0],
                x0=0.20,
                fprime=lambda x: f(x)[1],
                tol=1e-8,
                maxiter=50
            )
        except RuntimeError:
            return float('nan')

    def implied_volatility(
        call_price, spot, strike, time_to_expiry, max_iterations=200, tolerance=1e-10
    ):
        low_vol = 0.01
        high_vol = 1.0
        volatility = (low_vol + high_vol) / 2.0 
        for _ in range(max_iterations):
            estimated_price = BlackScholesGreeks.call_price(
                spot, strike, time_to_expiry, volatility
            )
            diff = estimated_price - call_price
            if abs(diff) < tolerance:
                break
            elif diff > 0:
                high_vol = volatility
            else:
                low_vol = volatility
            volatility = (low_vol + high_vol) / 2.0
        return volatility
    
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
    
    def calculate_total_delta_exposure(self, state, volcanic_rock_mid_price, pending_orders=None):
        total_delta = 0
        pending_quantities = {voucher: 0 for voucher in [
            VOLCANIC_ROCK_VOUCHER_9500,
            VOLCANIC_ROCK_VOUCHER_9750,
            VOLCANIC_ROCK_VOUCHER_10000,
            VOLCANIC_ROCK_VOUCHER_10250,
            VOLCANIC_ROCK_VOUCHER_10500
        ]}
        if pending_orders:
            for product, orders in pending_orders.items():
                if product in pending_quantities:
                    for order in orders:
                        pending_quantities[product] += order.quantity
        
        for voucher in pending_quantities.keys():
            if voucher in VOLCANIC_PARAMS:
                position = state.position.get(voucher, 0)
                
                total_position = position + pending_quantities[voucher]
                if total_position != 0:
                    tte = (
                        TIME_TO_EXPIRY
                        - (state.timestamp) / 1000000 / 252
                    )
                    volatility = VOLCANIC_PARAMS[voucher].get("current_volatility")
                    delta = BlackScholesGreeks.delta(
                        volcanic_rock_mid_price,
                        VOLCANIC_PARAMS[voucher]["strike"],
                        tte,
                        volatility
                    )
                    total_delta += delta * total_position
        return total_delta
    
    def update_active_vouchers(self, volcanic_rock_mid_price):
        active_vouchers = []
        atm_strike = round(volcanic_rock_mid_price / 250) * 250  
        for strike in [9500, 9750, 10000, 10250, 10500]:
            if strike <= atm_strike - 700: 
                continue
            elif abs(strike - volcanic_rock_mid_price) < 700: 
                active_vouchers.append(f"VOLCANIC_ROCK_VOUCHER_{strike}")
            elif strike > volcanic_rock_mid_price + 1000:  
                active_vouchers.append(f"VOLCANIC_ROCK_VOUCHER_{strike}")
                break
        return active_vouchers
    def get_voucher_mid_price(self, voucher_order_depth, trader_data):
        if voucher_order_depth.buy_orders and voucher_order_depth.sell_orders:
            best_bid = max(voucher_order_depth.buy_orders.keys())
            best_ask = min(voucher_order_depth.sell_orders.keys())
            mid_price = (best_bid + best_ask) / 2
            trader_data["prev_voucher_price"] = mid_price
            return mid_price
        elif trader_data["prev_voucher_price"] > 0:
            return trader_data["prev_voucher_price"]
        return 0
    def classify_option_by_delta(self, delta):
        if abs(delta) > 0.995: 
            return "ultra_hedge"  
        elif abs(delta) > 0.8:  
            return "strong_hedge"
        elif abs(delta) > 0.6:
            return "moderate_hedge"
        else:  
            return "option" 
    def optimize_delta_hedging(self, state, volcanic_rock_mid_price, total_delta_exposure):
        hedging_candidates = []
        if VOLCANIC_ROCK in state.order_depths:
            hedging_candidates.append({
                'product': VOLCANIC_ROCK,
                'delta': 1.0, 
                'order_depth': state.order_depths[VOLCANIC_ROCK],
                'classification': 'ultra_hedge' 
            })
        tte = TIME_TO_EXPIRY - (state.timestamp) / 1000000 / 252
        for voucher in VOLCANIC_VOUCHERS:
            if voucher in state.order_depths:
                if voucher in VOLCANIC_PARAMS and VOLCANIC_PARAMS[voucher].get("current_volatility"):
                    volatility = VOLCANIC_PARAMS[voucher]["current_volatility"]
                    strike = VOLCANIC_PARAMS[voucher]["strike"]
                    delta = BlackScholesGreeks.delta(
                        volcanic_rock_mid_price,
                        strike,
                        tte,
                        volatility
                    )
                    classification = self.classify_option_by_delta(delta)
                    hedging_candidates.append({
                        'product': voucher,
                        'delta': delta,
                        'order_depth': state.order_depths[voucher],
                        'classification': classification
                    })
        scored_candidates = []
        for candidate in hedging_candidates:
            efficiency = self.calculate_hedge_efficiency(
                candidate['product'],
                candidate['order_depth'],
                candidate['delta']
            )
            if efficiency:
                scored_candidates.append({**candidate, **efficiency})
        scored_candidates.sort(key=lambda x: x['efficiency_score'])
        return self.generate_optimal_hedging_orders(scored_candidates, total_delta_exposure, state)

    def calculate_hedge_efficiency(self, product, order_depth, delta):
        if order_depth.buy_orders and order_depth.sell_orders:
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            spread = best_ask - best_bid
            spread_percentage = spread / ((best_ask + best_bid) / 2)
            
            if delta > 0:
                cost_per_delta = best_ask / delta
            else:
                cost_per_delta = best_bid / abs(delta)  
                
            bid_volume = sum(order_depth.buy_orders.values())
            ask_volume = sum(abs(vol) for vol in order_depth.sell_orders.values())
            liquidity_score = (bid_volume + ask_volume) / 2
            efficiency_score = cost_per_delta * (1 + spread_percentage * 2)
            
            return {
                'product': product,
                'delta': delta,
                'cost_per_delta': cost_per_delta,
                'spread_percentage': spread_percentage,
                'liquidity_score': liquidity_score,
                'efficiency_score': efficiency_score
            }
        return None
    
    def generate_optimal_hedging_orders(self, scored_candidates, total_delta_exposure, state):
        hedging_orders = {}
        remaining_delta = -total_delta_exposure  # Delta we need to hedge
        if np.abs(remaining_delta) < 30:
            return hedging_orders
        ultra_hedge_candidates = [c for c in scored_candidates 
                                if c.get('classification') == 'ultra_hedge']
        
        for candidate in ultra_hedge_candidates:
            product = candidate['product']
            delta = candidate['delta']
            order_depth = candidate['order_depth']
            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue
            position_limit = POSITION_LIMITS[product]
            current_position = state.position.get(product, 0)
            if remaining_delta > 0:  
                best_ask = min(order_depth.sell_orders.keys())
                available_volume = -order_depth.sell_orders[best_ask]

                max_buy_quantity = min(
                    available_volume,
                    position_limit - current_position
                )
            
                delta_acquired = max_buy_quantity * delta
                
                if delta_acquired > remaining_delta:
                    adjusted_quantity = int(remaining_delta / delta)
                    quantity_to_buy = min(adjusted_quantity, max_buy_quantity)
                else:
                    quantity_to_buy = max_buy_quantity
                    
                if quantity_to_buy > 0:
                    if product not in hedging_orders:
                        hedging_orders[product] = []
                    hedging_orders[product].append(Order(product, best_ask, quantity_to_buy))
                    remaining_delta -= quantity_to_buy * delta
            else:
                best_bid = max(order_depth.buy_orders.keys())
                available_volume = order_depth.buy_orders[best_bid]
                
                max_sell_quantity = min(
                    available_volume,
                    position_limit + current_position
                )
                
                delta_removed = max_sell_quantity * delta
                
                if delta_removed > abs(remaining_delta):
                    adjusted_quantity = int(abs(remaining_delta) / delta)
                    quantity_to_sell = min(adjusted_quantity, max_sell_quantity)
                else:
                    quantity_to_sell = max_sell_quantity
                    
                if quantity_to_sell > 0:
                    if product not in hedging_orders:
                        hedging_orders[product] = []
                    hedging_orders[product].append(Order(product, best_bid, -quantity_to_sell))
                    remaining_delta += quantity_to_sell * delta
            
            if abs(remaining_delta) < 0.1:
                break
        return hedging_orders
    
    def calculate_implied_volatility(self, option_price, spot_price, strike, tte, voucher, trader_data):
        try:
            if option_price <= spot_price-strike:
                raise ValueError("Option price is too low")
            current_iv = BlackScholesGreeks.implied_volatility(
                option_price, 
                spot_price, 
                strike, 
                tte
            )
        except:
            current_iv = trader_data[voucher].get("last_iv", 0.16)
        if not np.isnan(current_iv):
            trader_data[voucher]["iv_history"].append(current_iv)
            if len(trader_data[voucher]["iv_history"]) > 20:
                trader_data[voucher]["iv_history"].pop(0)
        
        if len(trader_data[voucher]["iv_history"])== 20:
            rolling_iv = np.median(trader_data[voucher]["iv_history"])
        else:
            rolling_iv = current_iv
        
        trader_data[voucher]["last_iv"] = current_iv
        
        return rolling_iv
    
    def market_make(
        self,
        product: str,
        orders: List[Order],
        bid: int,
        ask: int,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
    ):
        buy_quantity = POSITION_LIMITS[product] - (position + buy_order_volume)
        if buy_quantity > 0:
            orders.append(Order(product, round(bid), buy_quantity))  # Buy order

        sell_quantity = POSITION_LIMITS[product] + (position - sell_order_volume)
        if sell_quantity > 0:
            orders.append(Order(product, round(ask), -sell_quantity))  # Sell order
        return buy_order_volume, sell_order_volume
    
    def make_orders(
        self,
        product,
        order_depth: OrderDepth,
        fair_value: float,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
        disregard_edge: float,  
        join_edge: float,  
        default_edge: float, 
        manage_position: bool = False,
        soft_position_limit: int = 0,
    
    ):
        orders: List[Order] = []
        asks_above_fair = [
            price
            for price in order_depth.sell_orders.keys()
            if price > fair_value + disregard_edge
        ]
        bids_below_fair = [
            price
            for price in order_depth.buy_orders.keys()
            if price < fair_value - disregard_edge
        ]
        best_ask_above_fair = min(asks_above_fair) if len(asks_above_fair) > 0 else None
        best_bid_below_fair = max(bids_below_fair) if len(bids_below_fair) > 0 else None

        ask = round(fair_value + default_edge)
        if best_ask_above_fair != None:
            if abs(best_ask_above_fair - fair_value) <= join_edge:
                ask = best_ask_above_fair 
            else:
                ask = best_ask_above_fair - 1 
        bid = round(fair_value - default_edge)
        if best_bid_below_fair != None:
            if abs(fair_value - best_bid_below_fair) <= join_edge:
                bid = best_bid_below_fair
            else:
                bid = best_bid_below_fair + 1

        if manage_position:
            if position > soft_position_limit:
                ask -= 1
            elif position < -1 * soft_position_limit:
                bid += 1
                
        buy_order_volume, sell_order_volume = self.market_make(
            product,
            orders,
            bid,
            ask,
            position,
            buy_order_volume,
            sell_order_volume,
        )
        return orders, buy_order_volume, sell_order_volume
    
    def volcanic_voucher_orders(self, voucher, voucher_order_depth, voucher_position, trader_data, volatility, delta, total_delta_exposure, theoretical_value):
        take_orders = []
        make_orders = []
        position_limit = POSITION_LIMITS[voucher]
        remaining_delta_capacity = POSITION_LIMITS[VOLCANIC_ROCK] - abs(total_delta_exposure)
        if voucher_order_depth.buy_orders and voucher_order_depth.sell_orders:
            best_bid = max(voucher_order_depth.buy_orders.keys())
            best_ask = min(voucher_order_depth.sell_orders.keys())
            trader_data["last_theoretical_price"] = theoretical_value
            max_buy_quantity = min(
                position_limit - voucher_position,
                int(remaining_delta_capacity / abs(delta)) if delta != 0 else position_limit
            )
            
            max_sell_quantity = min(
                position_limit + voucher_position,
                int(remaining_delta_capacity / abs(delta)) if delta != 0 else position_limit
            )

            buy_order_qty = 0
            sell_order_qty = 0
            if best_bid > theoretical_value + VOLCANIC_PARAMS[voucher]["take_width"] and max_sell_quantity > 0:
                quantity = min(
                    voucher_order_depth.buy_orders[best_bid],
                    max_sell_quantity
                )
                if quantity > 0:
                    take_orders.append(Order(voucher, best_bid, -quantity))
                sell_order_qty += abs(quantity)
                    
            if best_ask < theoretical_value - VOLCANIC_PARAMS[voucher]["take_width"] and max_buy_quantity > 0:
                quantity = min(
                    -voucher_order_depth.sell_orders[best_ask],
                    max_buy_quantity
                )  
                if quantity > 0:
                    take_orders.append(Order(voucher, best_ask, quantity))
                buy_order_qty += abs(quantity)
            
            make_orders, _, _ = self.make_orders(
                voucher,
                voucher_order_depth,
                theoretical_value,
                voucher_position,
                buy_order_qty,
                sell_order_qty,
                VOLCANIC_PARAMS[voucher]["disregard_edge"],
                VOLCANIC_PARAMS[voucher]["join_edge"],
                VOLCANIC_PARAMS[voucher]["default_edge"],
                False,
                VOLCANIC_PARAMS[voucher].get("soft_position_limit", 0),
                )
        
        return take_orders, make_orders
    
    def volcanic_rock_strategy(self, state: TradingState, traderObject) -> List[Order]:    
        volcanic_rock_order_depth = state.order_depths[VOLCANIC_ROCK]
        volcanic_rock_mid_price = (
            max(volcanic_rock_order_depth.buy_orders.keys()) +
            min(volcanic_rock_order_depth.sell_orders.keys())
        ) / 2
        
        volcanic_results = {}
        pending_orders = {}
        
        total_delta_exposure = self.calculate_total_delta_exposure(state, volcanic_rock_mid_price)
        valid_vouchers = self.update_active_vouchers(volcanic_rock_mid_price)
        for voucher in valid_vouchers:
            if voucher in VOLCANIC_PARAMS and voucher in state.order_depths:
                voucher_position = (
                    state.position[voucher]
                    if voucher in state.position
                    else 0
                )
                if voucher not in traderObject:
                    traderObject[voucher] = {
                        "prev_voucher_price": 0,
                        "iv_history": [],
                        "last_iv": VOLCANIC_PARAMS[voucher].get("ivolatility"),
                        "last_theoretical_price": 0
                    }
                voucher_order_depth = state.order_depths[voucher]
                voucher_mid_price = self.get_voucher_mid_price(
                    voucher_order_depth, 
                    traderObject[voucher]
                )
                tte = (
                    TIME_TO_EXPIRY
                    - (state.timestamp) / 1000000 / 252
                )
                volatility = self.calculate_implied_volatility(
                    voucher_mid_price,
                    volcanic_rock_mid_price,
                    VOLCANIC_PARAMS[voucher]["strike"],
                    tte,
                    voucher,
                    traderObject
                )
                VOLCANIC_PARAMS[voucher]["current_volatility"] = volatility
                delta = BlackScholesGreeks.delta(
                    volcanic_rock_mid_price,
                    VOLCANIC_PARAMS[voucher]["strike"],
                    tte,
                    volatility
                )

                theoretical_value = BlackScholesGreeks.call_price(
                    volcanic_rock_mid_price,
                    VOLCANIC_PARAMS[voucher]["strike"],
                    tte,
                    volatility
                )
                voucher_take_orders, voucher_make_orders = self.volcanic_voucher_orders(
                    voucher,
                    voucher_order_depth,
                    voucher_position,
                    traderObject[voucher],
                    volatility,
                    delta,
                    total_delta_exposure,
                    theoretical_value
                )
                
                for order in voucher_take_orders:
                    total_delta_exposure += delta * order.quantity
                
                if voucher_take_orders or voucher_make_orders:
                    pending_orders[voucher] = voucher_take_orders
                    volcanic_results[voucher] = voucher_take_orders + voucher_make_orders
        
        total_delta_exposure = self.calculate_total_delta_exposure(
            state, 
            volcanic_rock_mid_price, 
            pending_orders
        )
        
        hedging_orders = self.optimize_delta_hedging(
            state,
            volcanic_rock_mid_price,
            total_delta_exposure
        )

        for product, orders in hedging_orders.items():
            if product not in volcanic_results:
                volcanic_results[product] = []
            volcanic_results[product].extend(orders)
            
        return (volcanic_results.get(VOLCANIC_ROCK, []), 
                volcanic_results.get(VOLCANIC_ROCK_VOUCHER_9500, []), 
                volcanic_results.get(VOLCANIC_ROCK_VOUCHER_9750, []), 
                volcanic_results.get(VOLCANIC_ROCK_VOUCHER_10000, []), 
                volcanic_results.get(VOLCANIC_ROCK_VOUCHER_10250, []), 
                volcanic_results.get(VOLCANIC_ROCK_VOUCHER_10500, []),
                traderObject
            )
        
    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        """
        Takes all orders for all symbols as an input and outputs a list of orders to be sent
        """
        result = {}
        # traderData = "SAMPLE"
        conversions = 1
        
        traderObject = {}
        if state.traderData != None and state.traderData != "":
            traderObject = jsonpickle.decode(state.traderData)
        
        for product in state.order_depths:
            match product:
                case "KELP":
                    result[KELP] = self.kelp_strategy(state)
                case "RAINFOREST_RESIN":
                    result[RESIN] = self.resin_strategy(state)
                # case "SQUID_INK":
                #     result[SQUID_INK] = self.squid_try(state)
                case "PICNIC_BASKET1":
                    result[PCB1] = self.basket1_strategy(state)
                case "PICNIC_BASKET2":
                    result[PCB2] = self.basket2_strategy(state)
                case "VOLCANIC_ROCK":
                    result[VOLCANIC_ROCK], \
                        result[VOLCANIC_ROCK_VOUCHER_9500], \
                        result[VOLCANIC_ROCK_VOUCHER_9750], \
                        result[VOLCANIC_ROCK_VOUCHER_10000], \
                        result[VOLCANIC_ROCK_VOUCHER_10250], \
                        result[VOLCANIC_ROCK_VOUCHER_10500], \
                        traderObject = self.volcanic_rock_strategy(state, traderObject)
        traderData = jsonpickle.encode(traderObject)
        return result, conversions, traderData