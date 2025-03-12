import json
import pandas as pd
import sys
import matplotlib.pyplot as plt
from datamodel import TradingState, Order
from extractor import trading_states
from pathlib import Path
from importlib import import_module
from matcher import match_buy_order, match_sell_order

VERBOSE = False
DISPLAY_LENGTH = None

PRODUCTS = ["RAINFOREST_RESIN", "KELP"]
POSITION_LIMITS = {
    "RAINFOREST_RESIN": 100,
    "KELP": 100
}

def parse_algorithm(algo_path: str):
    algorithm_path = Path(algo_path).expanduser().resolve()
    if not algorithm_path.is_file():
        raise ModuleNotFoundError(f"{algorithm_path} is not a file.")
    
    sys.path.append(str(algorithm_path.parent))
    return import_module(algorithm_path.stem)

def print_self_trade(trade):
    if trade.seller == "SUBMISSION":
        print(f"Sold {trade.quantity} {trade.symbol} at {trade.price}.")
    elif trade.buyer == "SUBMISSION":
        print(f"Bought {trade.quantity} {trade.symbol} at {trade.price}.")

def plot_pnl(pnl_over_time):
    if not pnl_over_time:
        print("No PnL data available to plot.")
        return

    timestamps, pnl_values = zip(*pnl_over_time)
    
    plt.figure(figsize=(10, 6))
    plt.plot(timestamps, pnl_values, marker="o")
    plt.xlabel("Timestamp")
    plt.ylabel("Profit and Loss")
    plt.title("PnL Over Time")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("results/pnl_over_time.png")

def main() -> None:
    algo_path = "algorithms/algo.py"
    trader_module = parse_algorithm(algo_path)
    
    trader = trader_module.Trader()
    trader.cash = 0
    trader.pnl = 0
    
    position = {prod: 0 for prod in PRODUCTS}
    traderData = None

    pnl_over_time = []
    log_data = []

    for i, state in enumerate(trading_states):
        next_state = trading_states[i + 1] if i < len(trading_states) - 1 else None
        timestamp = state.timestamp

        state.position = position
        state.traderData = traderData  # Persist trader data

        # Capture sandbox log and trading results
        sandbox_log = trader.run(state)
        result, conversions, traderData = sandbox_log

        executed_trades = []
        for product, orders_list in result.items():
            for order in orders_list:
                trades_executed = []
                if order.quantity > 0:
                    trades_executed = match_buy_order(state, next_state, order)
                elif order.quantity < 0:
                    trades_executed = match_sell_order(state, next_state, order)

                for trade in trades_executed:
                    executed_trades.append((trade.symbol, trade.price, trade.quantity))

        # Compute PnL
        trader.pnl = trader.cash
        for product, pos in position.items():
            mid_price = (max(state.order_depths[product].buy_orders) + min(state.order_depths[product].sell_orders)) / 2
            trader.pnl += pos * mid_price
        
        pnl_over_time.append((timestamp, trader.pnl))

        # Store logs in structured format
        lambda_log = {
            "executed_trades": executed_trades,
            "state": {
                "listings": state.listings,
                "market_trades": state.market_trades,
                "observations": state.observations,
                "order_depths": state.order_depths,
                "own_trades": state.own_trades,
                "position": state.position,
                "timestamp": state.timestamp,
                "traderData": traderData
            }
        }

        log_entry = {
            "timestamp": timestamp,
            "sandboxLog": json.dumps(sandbox_log),
            "lambdaLog": json.dumps(lambda_log, indent=2)
        }

        log_data.append(log_entry)

    # Export logs to CSV
    logs_df = pd.DataFrame(log_data)
    logs_df.to_csv("results/logs.csv", index=False)

    # Plot PnL
    plot_pnl(pnl_over_time)

    print("Exported logs.csv and PnL graph.")

if __name__ == "__main__":
    main()
