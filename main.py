import pandas as pd
import sys
from typing import List, Dict
from datamodel import TradingState, Order
from extractor import trading_states
from typing import Any, Optional
from pathlib import Path
from importlib import import_module, metadata, reload

def parse_algorithm(algo_path: str) -> Any:
    algorithm_path = Path(algo_path).expanduser().resolve()
    if not algorithm_path.is_file():
        raise ModuleNotFoundError(f"{algorithm_path} is not a file")
    
    sys.path.append(str(algorithm_path.parent))
    return import_module(algorithm_path.stem)

def main() -> None:
    algo_path = "algorithms/algo.py"
    trader_module = parse_algorithm(algo_path)
    trader = trader_module.Trader() # trader instance
    
    for state in trading_states:
        traderData = state.traderData
        timestamp = state.timestamp
        listings = state.listings
        order_depths = state.order_depths
        own_trades = state.own_trades
        market_trades = state.market_trades
        position = state.position
        observations = state.observations
        
        result, conversions, traderData = trader.run(state)
        
        for product, orders_list in result.items():
            print(product)
            for order in orders_list:
                pass

if __name__ == "__main__":
    main()