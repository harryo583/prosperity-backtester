from typing import Dict, List
from datamodel import TradingState, Order

class Trader:
    
    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        """
        Instead of executing trading strategies, print all available TradingState info for backtesting.
        """
        print(state.toJSON())
        
        result = {}
        traderData = "SAMPLE"
        conversions = 1
        
        return result, conversions, traderData