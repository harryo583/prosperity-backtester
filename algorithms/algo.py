from typing import Dict, List
from datamodel import OrderDepth, TradingState, Order


class Trader:
      
    def __init__(self):
        pass

    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        """
        Takes all orders for all symbols as an input and outputs a list of orders to be sent
        """
        result = {}
        traderData = "SAMPLE" 
        conversions = 1
        
        for product in state.order_depths:
            pass
        
        return result, conversions, traderData