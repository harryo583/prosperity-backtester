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
    
    def quoter(self, position, theo, midprice, spread, offset_inflation_factor, deflection_limit, soft_limiter_volume) -> Tuple[float]:
        """ Prices the market maker bid and ask """
        offset = offset_inflation_factor * spread / 2
        order_imbalance = self.linear_clamp(- position * midprice / soft_limiter_volume, -1, 1)
        deflection = order_imbalance * deflection_limit
                
        bid_price = theo + offset * (deflection - 1)
        ask_price = theo + offset * (deflection - 1)
        
        volume = 0 # NOTE NEED TO CHANGE
        
        bid_volume = volume * (1 + order_imbalance)
        ask_volume = volume * (1 - order_imbalance)
        
        bid_quantity = bid_volume / bid_price
        ask_quantity = ask_volume / ask_price
        
        return round(bid_price), round(bid_quantity), round(ask_price), round(ask_quantity)
        
    
    def squid_strategy_0(self, state: TradingState):
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
            best_ask_price = 'inf'
            
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
            mm_best_ask_price = max(market_maker_asks.keys())
        
            mm_midprice = (mm_best_bid_price + mm_best_ask_price) // 2
            mm_vwap = 
        
        offset_inflation_factor = 1.3
        quoting_volume = 10
        soft_limiting_volume = 20
        min_flux = 0.5
        deflection_limit = -1
        ewma_alpha = 0.5
        size_threshold = 12
        
        if orderbook.sell_orders and orderbook.buy_orders:
            best_ask_price = min(orderbook.sell_orders.keys())
            best_bid_price = max(orderbook.buy_orders.keys())
            best_ask_volume = -orderbook.sell_orders[best_ask_price]
            best_bid_volume = orderbook.buy_orders[best_bid_price]
            
            midprice = (best_ask_price + best_bid_price) / 2
            volume_weighted_midprice = (best_ask_price * best_ask_volume + best_bid_price * best_bid_volume) // (best_ask_volume + best_bid_volume)
                    
            voluminous_bids = (price for price, vol in orderbook.buy_orders.items() if vol >= size_threshold)
            voluminous_asks = (price for price, vol in orderbook.sell_orders.items() if -vol >= size_threshold)
            market_maker_bid = min(voluminous_bids, default=best_bid_price)
            market_maker_ask = min(voluminous_asks, default=best_ask_price)
            
            filtered_midprice = (market_maker_bid + market_maker_ask) / 2
            
            self.squid_midprice_cache.append(midprice)
            self.squid_vwap_cache.append(volume_weighted_midprice)
            
            bid_price, bid_quantity, ask_price, ask_quantity = \
                self.quoter(position,
                            midprice, # theo
                            midprice, # midprice
                            best_ask_price - best_bid_price, # spread
                            offset_inflation_factor,
                            deflection_limit,
                            soft_limiting_volume)
            
            buy_quantity = min(best_ask_volume, POS_LIMIT_KELP - position)
            if buy_quantity > 0:
                orders.append(Order(KELP, bid_price, buy_quantity))
                total_buy_volume += buy_quantity
            
            sell_quantity = min(best_bid_volume, POS_LIMIT_KELP + position)
            if sell_quantity > 0:
                orders.append(Order(KELP, ask_price, -sell_quantity))
                total_sell_volume += sell_quantity
            
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