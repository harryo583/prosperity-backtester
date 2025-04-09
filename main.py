# main.py

import io
import sys
import json
import contextlib
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from importlib import import_module
from matcher import match_buy_order, match_sell_order
from datamodel import TradingState, Listing, OrderDepth, Trade, Observation, ConversionObservation

ROUND_NUMBER = 1
PRODUCTS = ["RAINFOREST_RESIN", "KELP", "SQUID_INK"]
POSITION_LIMITS = {
    "RAINFOREST_RESIN": 50,
    "KELP": 50,
    "SQUID_INK": 50
}

def load_trading_states(log_path: str):
    """Load trading states from a JSON log file and convert each dictionary into a TradingState object."""
    with open(log_path, "r") as f:
        trading_states_data = json.load(f)
    
    def convert_trading_state(d):
        # Convert listings
        listings = {}
        for sym, data in d.get("listings", {}).items():
            listings[sym] = Listing(
                symbol=data["symbol"],
                product=data["product"],
                denomination=data["denomination"]
            )
        
        # Convert order depths
        order_depths = {}
        for sym, data in d.get("order_depths", {}).items():
            od = OrderDepth()
            od.buy_orders = {int(k): int(v) for k, v in data.get("buy_orders", {}).items()}
            od.sell_orders = {int(k): int(v) for k, v in data.get("sell_orders", {}).items()}
            order_depths[sym] = od
        
        # Convert trades
        def convert_trades(trades):
            return [
                Trade(
                    symbol=t["symbol"],
                    price=int(t["price"]),
                    quantity=int(t["quantity"]),
                    buyer=t.get("buyer"),
                    seller=t.get("seller"),
                    timestamp=int(t["timestamp"])
                ) for t in trades
            ]
        market_trades = {}
        for sym, trades in d.get("market_trades", {}).items():
            market_trades[sym] = convert_trades(trades)
        own_trades = {}
        for sym, trades in d.get("own_trades", {}).items():
            own_trades[sym] = convert_trades(trades)
        
        # Convert position
        position = {prod: int(val) for prod, val in d.get("position", {}).items()}
        
        # Convert observations
        obs = d.get("observations", {})
        plain_obs = {prod: int(val) for prod, val in obs.get("plainValueObservations", {}).items()}
        conv_obs_data = obs.get("conversionObservations", {})
        conv_obs = {}
        for prod, details in conv_obs_data.items():
            conv_obs[prod] = ConversionObservation(
                bidPrice=float(details.get("bidPrice", 0.0)),
                askPrice=float(details.get("askPrice", 0.0)),
                transportFees=float(details.get("transportFees", 0.0)),
                exportTariff=float(details.get("exportTariff", 0.0)),
                importTariff=float(details.get("importTariff", 0.0)),
                sugarPrice=float(details.get("sugarPrice", 0.0)),
                sunlightIndex=float(details.get("sunlightIndex", 0.0))
            )
        observations = Observation(
            plainValueObservations=plain_obs,
            conversionObservations=conv_obs
        )
        # Create and return the TradingState object
        return TradingState(
            traderData=d.get("traderData", ""),
            timestamp=int(d.get("timestamp", 0)),
            listings=listings,
            order_depths=order_depths,
            own_trades=own_trades,
            market_trades=market_trades,
            position=position,
            observations=observations
        )
    return [convert_trading_state(d) for d in trading_states_data]



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
    """
    Plots the PnL over time.
    """
    if not pnl_over_time:
        print("No PnL data available to plot.")
        return

    # Unpack timestamps and pnl values
    timestamps, pnl_values = zip(*pnl_over_time)
    
    plt.figure(figsize=(10, 6))
    plt.plot(timestamps, pnl_values, marker="o", markersize=2)
    plt.xlabel("Timestamp")
    plt.ylabel("Profit and Loss")
    plt.title("PnL Over Time")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(f"results/round-{ROUND_NUMBER}/day-{day_number}/pnl_over_time.png")



def main(algo_path=None) -> None:
    if not algo_path:
        print("No algo path provided, using algorithms/algo.py")
        algo_path = "algorithms/algo.py"
    
    trader_module = parse_algorithm(algo_path)
    
    trader = trader_module.Trader()  # trader instance
    trader.cash = {prod: 0 for prod in PRODUCTS}  # initial cash
    trader.pnl = {prod: 0 for prod in PRODUCTS}  # initial pnl
    trader.aggregate_cash = 0
    trader.aggregate_pnl = 0
    
    # Containers for exporting CSVs and tracking PnL
    market_conditions = []  # list of dicts for market conditions snapshot
    trade_history_list = []  # list of dicts for each trade
    sandbox_logs = [] # list to store sandbox logs
    pnl_over_time = []  # list of (timestamp, pnl)
    
    # Variables to keep track of trader logs
    position = {prod: 0 for prod in PRODUCTS}
    traderData = ""

    for i, state in enumerate(trading_states):
        next_state = trading_states[i + 1] if i < len(trading_states) - 1 else None
        timestamp = state.timestamp
        traded = False
        all_trades_executed = []
        
        if LOG_LENGTH and timestamp > LOG_LENGTH * 100:
            break

        # Update the state with newest trader data
        state.position = position
        state.traderData = traderData  # traderData from previous run
        
        # lambda_buffer = io.StringIO()
        
        # with contextlib.redirect_stdout(lambda_buffer):  # redirect stdout to buffer
        #     result, conversions, traderData = trader.run(state)
        # lambda_log = lambda_buffer.getvalue()
        
        result, conversions, traderData = trader.run(state)
        lambda_log = ""
        
        sandbox_logs.append({
            "sandboxLog": "",
            "lambdaLog": lambda_log,
            "timestamp": timestamp
        })
        
        for product, orders_list in result.items():
            current_position = position.get(product, 0)
            total_buy = sum(order.quantity for order in orders_list if order.quantity > 0)
            total_sell = sum(-order.quantity for order in orders_list if order.quantity < 0)
            pos_limit = POSITION_LIMITS.get(product, 0)

            if current_position + total_buy > pos_limit or current_position - total_sell < -pos_limit:
                if VERBOSE:
                    print(f"[{timestamp}] Position limit exceeded for {product}. Cancelling all orders.")
                continue

            # Process each order by matching against order depths
            for order in orders_list:
                trades_executed = []
                if order.quantity > 0:  # buy order
                    trades_executed = match_buy_order(state, next_state, order)
                    total_filled = sum(trade.quantity for trade in trades_executed)
                    position[product] = position.get(product, 0) + total_filled  # update trader position
                    cash_change = -sum(trade.price * trade.quantity for trade in trades_executed)
                    trader.cash[product] += cash_change # update cash
                    trader.aggregate_cash += cash_change # update cash
                elif order.quantity < 0:  # sell order
                    trades_executed = match_sell_order(state, next_state, order)
                    total_filled = sum(trade.quantity for trade in trades_executed)
                    position[product] = position.get(product, 0) - total_filled  # update trader position
                    cash_change = sum(trade.price * trade.quantity for trade in trades_executed)
                    trader.cash[product] += cash_change
                    trader.aggregate_cash += cash_change # update cash
                
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
                
                if trades_executed:
                    all_trades_executed.extend(trades_executed)
                
                if LOG_LENGTH and trades_executed and timestamp < LOG_LENGTH * 100:
                    traded = True
                    if VERBOSE:
                        print(f"Executed trades for order {order}: {trades_executed}")
        
        trader.pnl = trader.cash.copy()
        trader.aggregate_pnl = trader.aggregate_cash
        
        for product, pos in position.items():
            mid_price = (max(state.order_depths[product].buy_orders) + min(state.order_depths[product].sell_orders)) / 2
            trader.pnl[product] += pos * mid_price
            trader.aggregate_pnl += pos * mid_price
            
        if traded and LOG_LENGTH and timestamp < LOG_LENGTH * 100:
            print(f"[{timestamp}]")
            for trade in all_trades_executed:
                print_self_trade(trade)
            print(f"Positions: {state.position}")
            print(f"Cash: {trader.aggregate_cash}")
            print(f"PNL: {trader.aggregate_pnl}\n")
        
        # Record pnl over time
        pnl_over_time.append((timestamp, trader.aggregate_pnl))
        
        # Record market condition snapshot for each product
        for product in PRODUCTS:
            day = -1
            ts = state.timestamp
            od = state.order_depths.get(product, None)
            if od is not None:
                bids = sorted(od.buy_orders.items(), key=lambda x: x[0], reverse=True)  # top 3 bids
                asks = sorted(od.sell_orders.items(), key=lambda x: x[0])  # top 3 asks
            else:
                bids = []
                asks = []
            
            bid_price_1, bid_vol_1 = bids[0] if len(bids) > 0 else ("", "")
            bid_price_2, bid_vol_2 = bids[1] if len(bids) > 1 else ("", "")
            bid_price_3, bid_vol_3 = bids[2] if len(bids) > 2 else ("", "")

            ask_price_1, ask_vol_1 = asks[0] if len(asks) > 0 else ("", "")
            ask_price_2, ask_vol_2 = asks[1] if len(asks) > 1 else ("", "")
            ask_price_3, ask_vol_3 = asks[2] if len(asks) > 2 else ("", "")
            
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
                "profit_and_loss": trader.aggregate_pnl
            })
    
    # Export market conditions and trade history to CSV files with semicolon delimiter
    market_conditions_df = pd.DataFrame(market_conditions)
    market_conditions_df = market_conditions_df[[
        "day", "timestamp", "product",
        "bid_price_1", "bid_volume_1", "bid_price_2", "bid_volume_2", "bid_price_3", "bid_volume_3",
        "ask_price_1", "ask_volume_1", "ask_price_2", "ask_volume_2", "ask_price_3", "ask_volume_3",
        "mid_price", "profit_and_loss"
    ]]
    market_conditions_df.to_csv(f"results/round-{ROUND_NUMBER}/day-{day_number}/orderbook.csv", sep=";", index=False)
    
    trade_history_df = pd.DataFrame(trade_history_list)
    if not trade_history_df.empty:
        trade_history_df = trade_history_df[["timestamp", "buyer", "seller", "symbol", "currency", "price", "quantity"]]
    trade_history_df.to_csv(f"results/round-{ROUND_NUMBER}/day-{day_number}/trade_history.csv", sep=";", index=False)
    print("-----------------------------------------------------------------------------------")
    print("TOTAL PNL:", trader.aggregate_pnl)
    for product, pnl in trader.pnl.items():
        print(f"  {product}: {pnl}")
    print("Exported orderbook.csv and trade_history.csv.")
    print("-----------------------------------------------------------------------------------")
    
    combined_logs_path = f"results/round-{ROUND_NUMBER}/day-{day_number}/combined_results.log"
    with open(combined_logs_path, "w") as f:
        # Sandbox logs section
        f.write("Sandbox logs:\n")
        for log in sandbox_logs:
            f.write(json.dumps(log, indent=2) + "\n")
        f.write("\n")
        
        # Activities logs section
        f.write("Activities log:\n")
        header = ("day;timestamp;product;bid_price_1;bid_volume_1;bid_price_2;bid_volume_2;"
                  "bid_price_3;bid_volume_3;ask_price_1;ask_volume_1;ask_price_2;ask_volume_2;"
                  "ask_price_3;ask_volume_3;mid_price;profit_and_loss\n")
        f.write(header)
        for cond in market_conditions:
            line = (f"{cond['day']};{cond['timestamp']};{cond['product']};"
                    f"{cond['bid_price_1']};{cond['bid_volume_1']};"
                    f"{cond['bid_price_2']};{cond['bid_volume_2']};"
                    f"{cond['bid_price_3']};{cond['bid_volume_3']};"
                    f"{cond['ask_price_1']};{cond['ask_volume_1']};"
                    f"{cond['ask_price_2']};{cond['ask_volume_2']};"
                    f"{cond['ask_price_3']};{cond['ask_volume_3']};"
                    f"{cond['mid_price']};{cond['profit_and_loss']}\n")
            f.write(line)
        f.write("\n")
        
        # Trade history section
        f.write("Trade History:\n")
        f.write(json.dumps(trade_history_list, indent=2))
    
    plot_pnl(pnl_over_time)  # call plotting function


if __name__ == "__main__":
    # Expected optional arguments (in order):
    #   1. Round number (int between 0 and 5, defaults to 0)
    #   2. Algorithm path (defaults to "algorithms/algo.py")
    #   3. Log length (int, number of timestamps to backtest, defaults to all)
    #   4. Verbose (true/false, 1/0, yes/no; defaults to false)

    # Validate round number
    if len(sys.argv) > 1:
        try:
            day_number = int(sys.argv[1])
            if day_number < 0 or day_number > 2:
                raise ValueError("Round number must be between 0 and 3.")
        except ValueError as e:
            print(f"Invalid round number provided: {sys.argv[1]}. {e}")
            sys.exit(1)
    else:
        day_number = 0

    # Validate algorithm path
    if len(sys.argv) > 2:
        algo_path = sys.argv[2]
        algo_file = Path(algo_path).expanduser().resolve()
        if not algo_file.is_file():
            print(f"Algorithm file not found: {algo_path}")
            sys.exit(1)
        algo_path = str(algo_file)  # Use resolved path as string
    else:
        algo_path = "algorithms/algo.py"
        default_algo = Path(algo_path).expanduser().resolve()
        if not default_algo.is_file():
            print(f"Default algorithm file not found: {algo_path}")
            sys.exit(1)

    # Validate log length
    if len(sys.argv) > 3:
        try:
            LOG_LENGTH = int(sys.argv[3])
            if LOG_LENGTH <= 0:
                raise ValueError("Log length must be a positive integer.")
        except ValueError as e:
            print(f"Invalid log length provided: {sys.argv[3]}. {e}")
            sys.exit(1)
    else:
        LOG_LENGTH = None

    # Validate verbose flag
    if len(sys.argv) > 4:
        verbose_arg = sys.argv[4].lower()
        valid_verbose = ["true", "false", "1", "0", "yes", "no", "是", "否"]
        if verbose_arg not in valid_verbose:
            print(f"Invalid verbose flag provided: {sys.argv[4]}. Use true/false, 1/0, yes/no.")
            sys.exit(1)
        VERBOSE = verbose_arg in ["true", "1", "yes", "是"]
    else:
        VERBOSE = False

    # Check that the trading states file exists
    trading_states_file = f"data/round-{ROUND_NUMBER}/day-{day_number}/trading_states.json"
    if not Path(trading_states_file).expanduser().resolve().is_file():
        print(f"Trading states file not found: {trading_states_file}")
        sys.exit(1)

    trading_states = load_trading_states(trading_states_file)

    main(algo_path)