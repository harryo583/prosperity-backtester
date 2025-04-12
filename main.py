# main.py

import io
import sys
import json
import contextlib
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.colors as mcolors  # For color manipulation
from pathlib import Path
from importlib import import_module
from matcher import match_buy_order, match_sell_order
from datamodel import TradingState, Listing, OrderDepth, Trade, Observation, ConversionObservation

# Constants for round, products, etc.
ROUND_NUMBER = 2
SHOW_PLOT = True

PRODUCTS = ["RAINFOREST_RESIN", "KELP", "SQUID_INK", "CROISSANTS", "DJEMBES", "JAMS", "PICNIC_BASKET1", "PICNIC_BASKET2"]
RESIN = "RAINFOREST_RESIN"
KELP = "KELP"
SQUID_INK = "SQUID_INK"
CROISSANTS = "CROISSANTS"
DJEMBES = "DJEMBES"
JAMS = "JAMS"
PCB1 = "PICNIC_BASKET1"
PCB2 = "PICNIC_BASKET2"

CONSOLE_PRINT = True
POSITION_LIMITS = {
    "RAINFOREST_RESIN": 50,
    "KELP": 50,
    "SQUID_INK": 50,
    "CROISSANTS": 250,
    "JAM": 350,
    "DJEMBE": 60,
    "PICNIC_BASKET1": 60,
    "PICNIC_BASKET2": 100
}

DISPLAY_RESTING_QUOTES = True
QUOTES_DISPLAY_PRODUCTS = [SQUID_INK]

PRODUCT_COLORS = {
    "RAINFOREST_RESIN": "#1f77b4",
    "KELP": "#ff7f0e",
    "SQUID_INK": "#2ca02c",
    "CROISSANTS": "#d62728",
    "DJEMBES": "#9467bd",
    "JAMS": "#8c564b",
    "PICNIC_BASKET1": "#e377c2",
    "PICNIC_BASKET2": "#7f7f7f"
}

def lighten_color(color, amount=0.5):
    """
    Lightens the given color by mixing it with white.
    Input can be matplotlib color string, hex string, or RGB tuple.
    The amount parameter controls how much white is mixed in [0, 1].
    """
    try:
        c = mcolors.cnames[color]
    except KeyError:
        c = color
    c = mcolors.to_rgb(c)
    # Linearly interpolate between the color and white
    return [(1 - amount) * comp + amount for comp in c]


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


def plot_pnl(per_product_pnl, per_product_quotes=None):
    """
    Plots the PnL over time for each product using the left y-axis,
    and overlays resting quotes (if provided) on a secondary y-axis.
    The resting quotes for each product are drawn in a faded version of the product's assigned color.
    """
    if not per_product_pnl:
        print("No PnL data available to plot.")
        return

    # Create a figure and two y-axes sharing the same x-axis
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()
    
    # --- Plot resting quotes on the secondary y-axis ---
    if per_product_quotes:
        for product, quotes_data in per_product_quotes.items():
            if quotes_data:
                # Extract timestamp, bid and ask
                timestamps, bid_prices, ask_prices = zip(*quotes_data)
                bid_prices = [price if price is not None else np.nan for price in bid_prices]
                ask_prices = [price if price is not None else np.nan for price in ask_prices]
                # Retrieve the product's base color and create a faded version
                base_color = PRODUCT_COLORS.get(product, "grey")
                faded_color = lighten_color(base_color, 0.5)
                # Plot the filled area between bid and ask on ax2
                ax2.fill_between(timestamps, bid_prices, ask_prices, step='mid',
                                 color=faded_color, alpha=0.3, label=f"{product} Quotes")
                # Plot dashed lines for both bid and ask in the same (faded) color
                ax2.plot(timestamps, bid_prices, linestyle="--", color=faded_color, linewidth=1)
                ax2.plot(timestamps, ask_prices, linestyle="--", color=faded_color, linewidth=1)
    # ------------------------------------------------------
    
    # --- Plot the PnL data on the primary y-axis ---
    for product, pnl_data in per_product_pnl.items():
        if pnl_data:
            timestamps, pnl_values = zip(*pnl_data)
            prod_color = PRODUCT_COLORS.get(product, None)
            ax1.plot(timestamps, pnl_values, marker="o", markersize=2, label=product, color=prod_color)
    
    ax1.set_xlabel("Timestamp")
    ax1.set_ylabel("Profit and Loss")
    ax2.set_ylabel("Resting Quotes Price")
    ax1.set_title("PnL Over Time per Product")
    ax1.tick_params(axis="x", rotation=45)
    
    # Combine legends from both axes
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="best")
    
    fig.tight_layout()
    plt.savefig(f"results/round-{ROUND_NUMBER}/day-{day_number}/pnl_over_time.png")
    if SHOW_PLOT:
        plt.show()


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
    market_conditions = []      # list of dicts for market conditions snapshot
    trade_history_list = []     # list of dicts for each trade
    sandbox_logs = []           # list to store sandbox logs
    per_product_pnl = {prod: [] for prod in PRODUCTS}
    
    # Create container for quotes if the resting quotes display is enabled.
    if DISPLAY_RESTING_QUOTES:
        per_product_quotes = {prod: [] for prod in QUOTES_DISPLAY_PRODUCTS}
    
    position = {prod: 0 for prod in PRODUCTS}
    traderData = ""

    for i, state in enumerate(trading_states):
        next_state = trading_states[i + 1] if i < len(trading_states) - 1 else None
        timestamp = state.timestamp
        traded = False
        all_trades_executed = []
        
        mid_prices = {}
        for product in state.listings:
            mid_prices[product] = (min(state.order_depths[product].sell_orders.keys()) +
                                   max(state.order_depths[product].buy_orders.keys())) // 2
        
        if LOG_LENGTH and timestamp > LOG_LENGTH * 100:
            break
        
        state.position = position
        state.traderData = traderData
        
        if CONSOLE_PRINT:
            result, conversions, traderData = trader.run(state)
            lambda_log = ""
        else:
            lambda_buffer = io.StringIO()
            with contextlib.redirect_stdout(lambda_buffer):
                result, conversions, traderData = trader.run(state)
            lambda_log = lambda_buffer.getvalue()
        
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

            for order in orders_list:
                trades_executed = []
                if order.quantity > 0:  # buy order
                    trades_executed = match_buy_order(state, next_state, order)
                    total_filled = sum(trade.quantity for trade in trades_executed)
                    position[product] = position.get(product, 0) + total_filled
                    cash_change = -sum(trade.price * trade.quantity for trade in trades_executed)
                    trader.cash[product] += cash_change
                    trader.aggregate_cash += cash_change
                elif order.quantity < 0:  # sell order
                    trades_executed = match_sell_order(state, next_state, order)
                    total_filled = sum(trade.quantity for trade in trades_executed)
                    position[product] = position.get(product, 0) - total_filled
                    cash_change = sum(trade.price * trade.quantity for trade in trades_executed)
                    trader.cash[product] += cash_change
                    trader.aggregate_cash += cash_change
                
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
            trader.pnl[product] += pos * mid_prices[product]
            trader.aggregate_pnl += pos * mid_prices[product]
        
        for product in PRODUCTS:
            per_product_pnl[product].append((timestamp, trader.pnl.get(product, 0)))
        
        # --- Record resting quotes for specified products ---
        for product in PRODUCTS:
            day = -1
            ts = state.timestamp
            od = state.order_depths.get(product, None)
            if od is not None:
                bids = sorted(od.buy_orders.items(), key=lambda x: x[0], reverse=True)
                asks = sorted(od.sell_orders.items(), key=lambda x: x[0])
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
            
            # If the product is selected for quoting, record its best bid and ask
            if DISPLAY_RESTING_QUOTES and product in QUOTES_DISPLAY_PRODUCTS:
                best_bid = bids[0][0] if len(bids) > 0 else None
                best_ask = asks[0][0] if len(asks) > 0 else None
                per_product_quotes[product].append((ts, best_bid, best_ask))
        # ---------------------------------------------------------------------------
        
        if traded and LOG_LENGTH and timestamp < LOG_LENGTH * 100:
            print(f"[{timestamp}]")
            for trade in all_trades_executed:
                print_self_trade(trade)
            print(f"Positions: {state.position}")
            print(f"Cash: {trader.aggregate_cash}")
            print(f"PNL: {trader.aggregate_pnl}\n")
    
        # CSV export code (orderbook and trade history) remains unchanged...
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
        f.write("Sandbox logs:\n")
        for log in sandbox_logs:
            f.write(json.dumps(log, indent=2) + "\n")
        f.write("\n")
        
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
        
        f.write("Trade History:\n")
        f.write(json.dumps(trade_history_list, indent=2))
    
    pnl_file_path = f"grid_search_data/pnl.txt"
    with open(pnl_file_path, "w") as f:
        f.write(str(trader.aggregate_pnl))
        
    if DISPLAY_RESTING_QUOTES:
        plot_pnl(per_product_pnl, per_product_quotes)
    else:
        plot_pnl(per_product_pnl)


if __name__ == "__main__":
    # Expected optional arguments:
    #   1. Round number (int between 0 and 5, defaults to 0)
    #   2. Algorithm path (defaults to "algorithms/algo.py")
    #   3. Log length (int, number of timestamps to backtest, defaults to all)
    #   4. Verbose (true/false, 1/0, yes/no; defaults to false)

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

    if len(sys.argv) > 2:
        algo_path = sys.argv[2]
        algo_file = Path(algo_path).expanduser().resolve()
        if not algo_file.is_file():
            print(f"Algorithm file not found: {algo_path}")
            sys.exit(1)
        algo_path = str(algo_file)
    else:
        algo_path = "algorithms/algo.py"
        default_algo = Path(algo_path).expanduser().resolve()
        if not default_algo.is_file():
            print(f"Default algorithm file not found: {algo_path}")
            sys.exit(1)

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

    if len(sys.argv) > 4:
        verbose_arg = sys.argv[4].lower()
        valid_verbose = ["true", "false", "1", "0", "yes", "no", "是", "否"]
        if verbose_arg not in valid_verbose:
            print(f"Invalid verbose flag provided: {sys.argv[4]}. Use true/false, 1/0, yes/no.")
            sys.exit(1)
        VERBOSE = verbose_arg in ["true", "1", "yes", "是"]
    else:
        VERBOSE = False

    trading_states_file = f"data/round-{ROUND_NUMBER}/day-{day_number}/trading_states.json"
    if not Path(trading_states_file).expanduser().resolve().is_file():
        print(f"Trading states file not found: {trading_states_file}")
        sys.exit(1)

    trading_states = load_trading_states(trading_states_file)

    main(algo_path)
