from typing import Dict, List
from datamodel import OrderDepth, TradingState, Order

KELP = "KELP"
RESIN = "RAINFOREST_RESIN"

BUY = "BUY"
SELL = "SELL"

POS_LIMIT_KELP = 50
POS_LIMIT_RESIN = 50


class Trader:
      
    def __init__(self):
        pass
    
    def kelp_strategy(self):
        pass
    
    def resin_strategy(self, state: TradingState) -> List[Order]:
        position = state.position.get(RESIN, 0)
        order_depth = state.order_depths.get(RESIN, 0)
        
        orders: List[Order] = []
        
        if len(order_depth.buy_orders) != 0:
            theo = 10000
            bid_volume = POS_LIMIT_RESIN - position
            ask_volume = - position - POS_LIMIT_RESIN
            
            if position == 0:
                orders.append(Order(RESIN, theo - 1, bid_volume))
                orders.append(Order(RESIN, theo + 1, ask_volume))
            elif position > 0:
                orders.append(Order(RESIN, theo - 2, bid_volume))
                orders.append(Order(RESIN, theo, ask_volume))
            else:
                orders.append(Order(RESIN, theo, bid_volume))
                orders.append(Order(RESIN, theo + 2, ask_volume))
        
        return orders

    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        """
        Takes all orders for all symbols as an input and outputs a list of orders to be sent
        """
        result = {}
        traderData = "SAMPLE" 
        conversions = 1
        
        for product in state.order_depths:
            if product == RESIN:
                result[RESIN] = self.resin_strategy_backup(state)
        
        return result, conversions, traderData