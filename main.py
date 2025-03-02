# main.py

import pandas as pd
import sys
from datamodel import TradingState, Order
from extractor import trading_states
from pathlib import Path
from importlib import import_module, metadata, reload
from matcher import match_buy_order, match_sell_order

PRODUCTS = ["RAINFOREST_RESIN", "KELP"]

POSITION_LIMITS = {
    "RAINFOREST_RESIN": 100,
    "KELP": 100
}

def parse_algorithm(algo_path: str):
    algorithm_path = Path(algo_path).expanduser().resolve()
    if not algorithm_path.is_file():
        raise ModuleNotFoundError(f"{algorithm_path} is not a file")
    
    sys.path.append(str(algorithm_path.parent))
    return import_module(algorithm_path.stem)

def main() -> None:
    algo_path = "algorithms/algo.py"
    trader_module = parse_algorithm(algo_path)
    
    trader = trader_module.Trader() # trader instance
    trader.pnl = 0 # initial pnl
    
    for state in trading_states:
        timestamp = state.timestamp
        result, conversions, traderData = trader.run(state)
        
        for product, orders_list in result.items():
            current_position = state.position.get(product, 0)
            total_buy = sum(order.quantity for order in orders_list if order.quantity > 0)
            total_sell = sum(-order.quantity for order in orders_list if order.quantity < 0)
            pos_limit = POSITION_LIMITS.get(product, 0)
            
            if current_position + total_buy > pos_limit or current_position - total_sell < -pos_limit:
                print(f"[{timestamp}] Position limit exceeded for {product}. Cancelling all orders.")
                continue
            
            # Process each order by matching against order depths
            for order in orders_list:
                trades_executed = []
                if order.quantity > 0: # buy order
                    trades_executed = match_buy_order(state, order)
                    total_filled = sum(trade.quantity for trade in trades_executed)
                    state.position.setdefault(product, 0)
                    state.position[product] += total_filled # update trader position
                    trader.pnl -= sum(trade.price * trade.quantity for trade in trades_executed) # update pnl
                elif order.quantity < 0: # sell order
                    trades_executed = match_sell_order(state, order)
                    total_filled = sum(trade.quantity for trade in trades_executed)
                    state.position.setdefault(product, 0)
                    state.position[product] -= total_filled # update trader position
                    trader.pnl += sum(trade.price * trade.quantity for trade in trades_executed) # update pnl
                
                if trades_executed:
                    print(f"[{timestamp}] Executed trades for order {order}: {trades_executed}")
                else:
                    print(f"[{timestamp}] No trades executed for order {order}.")
        
        print(f"[{timestamp}] End of iteration: Positions: {state.position}, PnL: {trader.pnl}")


if __name__ == "__main__":
    main()