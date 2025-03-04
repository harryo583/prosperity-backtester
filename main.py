import pandas as pd
import sys
import matplotlib.pyplot as plt
from datamodel import TradingState, Order
from extractor import trading_states
from pathlib import Path
from importlib import import_module
from matcher import match_buy_order, match_sell_order

PRODUCTS = ["RAINFOREST_RESIN", "KELP"]

POSITION_LIMITS = {
    "RAINFOREST_RESIN": 100,
    "KELP": 100
}

VERBOSE = False
DISPLAY_LENGTH = 10

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

def plot_pnl_over_time(pnl_over_time):
    """
    Plots the PnL over time
    """
    if not pnl_over_time:
        print("No PnL data available to plot.")
        return

    # Unpack timestamps and pnl values
    timestamps, pnl_values = zip(*pnl_over_time)
    
    plt.figure(figsize=(10, 6))
    plt.plot(timestamps, pnl_values, marker="o")
    plt.xlabel("Timestamp")
    plt.ylabel("Profit and Loss")
    plt.title("PnL Over Time")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("results/pnl_over_time.png")  # saves the plot as a PNG file
    plt.show()


def main() -> None:
    algo_path = "algorithms/algo.py"
    trader_module = parse_algorithm(algo_path)
    
    trader = trader_module.Trader()  # trader instance
    trader.pnl = 0  # initial pnl
    
    # Containers for exporting CSVs and tracking PnL
    market_conditions = []  # list of dicts for market conditions snapshot
    trade_history_list = []  # list of dicts for each executed trade
    pnl_over_time = []  # list to track (timestamp, pnl)

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
                if order.quantity > 0:  # buy order
                    trades_executed = match_buy_order(state, order)
                    total_filled = sum(trade.quantity for trade in trades_executed)
                    state.position.setdefault(product, 0)
                    state.position[product] += total_filled  # update trader position
                    trader.pnl -= sum(trade.price * trade.quantity for trade in trades_executed)  # update pnl
                elif order.quantity < 0:  # sell order
                    trades_executed = match_sell_order(state, order)
                    total_filled = sum(trade.quantity for trade in trades_executed)
                    state.position.setdefault(product, 0)
                    state.position[product] -= total_filled  # update trader position
                    trader.pnl += sum(trade.price * trade.quantity for trade in trades_executed)  # update pnl
                
                # Record each executed trade in trade_history_list
                for trade in trades_executed:
                    trade_history_list.append({
                        "timestamp": trade.timestamp,
                        "buyer": trade.buyer,
                        "seller": trade.seller,
                        "symbol": trade.symbol,
                        "currency": "SEASHELLS",
                        "price": trade.price,
                        "quantity": trade.quantity
                    })
                
                if trades_executed and timestamp < DISPLAY_LENGTH * 100:
                    if VERBOSE:
                        print(f"[{timestamp}] Executed trades for order {order}: {trades_executed}")
                    else:
                        print(f"[{timestamp}]")
                        for trade in trades_executed:
                            print_self_trade(trade)
                elif VERBOSE and timestamp < DISPLAY_LENGTH * 100:
                    print(f"[{timestamp}] No trades executed for order {order}.")
        
        if timestamp < DISPLAY_LENGTH * 100:
            print(f"Positions: {state.position}")
            print(f"PNL: {trader.pnl}\n")
        
        # Record pnl over time for plotting
        pnl_over_time.append((timestamp, trader.pnl))
        
        # For each product, record a snapshot of the market conditions
        for product in PRODUCTS:
            day = -1
            ts = state.timestamp
            od = state.order_depths.get(product, None)
            if od is not None:
                # Get top 3 bid orders (buy_orders sorted descending by price)
                bids = sorted(od.buy_orders.items(), key=lambda x: x[0], reverse=True)
                # Get top 3 ask orders (sell_orders sorted ascending by price)
                asks = sorted(od.sell_orders.items(), key=lambda x: x[0])
            else:
                bids = []
                asks = []
            
            # Unpack up to 3 bids; if missing, use empty strings
            bid_price_1, bid_vol_1 = bids[0] if len(bids) > 0 else ("", "")
            bid_price_2, bid_vol_2 = bids[1] if len(bids) > 1 else ("", "")
            bid_price_3, bid_vol_3 = bids[2] if len(bids) > 2 else ("", "")

            # Unpack up to 3 asks
            ask_price_1, ask_vol_1 = asks[0] if len(asks) > 0 else ("", "")
            ask_price_2, ask_vol_2 = asks[1] if len(asks) > 1 else ("", "")
            ask_price_3, ask_vol_3 = asks[2] if len(asks) > 2 else ("", "")
            
            # Compute mid_price if both bid and ask exist
            if bids and asks:
                mid_price = (bids[0][0] + asks[0][0]) / 2.0
            else:
                mid_price = ""
            
            market_conditions.append({
                "day": day,
                "timestamp": ts,
                "product": product,
                "bid_price_1": bid_price_1,
                "bid_volume_1": bid_vol_1,
                "bid_price_2": bid_price_2,
                "bid_volume_2": bid_vol_2,
                "bid_price_3": bid_price_3,
                "bid_volume_3": bid_vol_3,
                "ask_price_1": ask_price_1,
                "ask_volume_1": ask_vol_1,
                "ask_price_2": ask_price_2,
                "ask_volume_2": ask_vol_2,
                "ask_price_3": ask_price_3,
                "ask_volume_3": ask_vol_3,
                "mid_price": mid_price,
                "profit_and_loss": trader.pnl
            })
    
    # Export market conditions and trade history to CSV files with semicolon delimiter
    market_conditions_df = pd.DataFrame(market_conditions)
    market_conditions_df = market_conditions_df[[
        "day", "timestamp", "product",
        "bid_price_1", "bid_volume_1", "bid_price_2", "bid_volume_2", "bid_price_3", "bid_volume_3",
        "ask_price_1", "ask_volume_1", "ask_price_2", "ask_volume_2", "ask_price_3", "ask_volume_3",
        "mid_price", "profit_and_loss"
    ]]
    
    market_conditions_df.to_csv("results/market_conditions.csv", sep=";", index=False)
    
    trade_history_df = pd.DataFrame(trade_history_list)
    trade_history_df = trade_history_df[["timestamp", "buyer", "seller", "symbol", "currency", "price", "quantity"]]
    trade_history_df.to_csv("results/trade_history.csv", sep=";", index=False)
    
    print("Exported market_conditions.csv and trade_history.csv")
    
    # Call the plotting function to generate the PnL over time graph
    plot_pnl_over_time(pnl_over_time)


if __name__ == "__main__":
    main()