import json
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from json import JSONDecoder
from datamodel import TradingState, Listing, OrderDepth, Trade, Observation, ConversionObservation

PRINT_TRADING_STATES = True
PRINT_ACTIVITY_LOGS = True
PRINT_TRADE_HISTORY = True

"""
1. Trade execution & order flow analysis
    - Trade frequency & volume
        - Count of trades (me & market)
        - Average trade size
        - Variance of trade size
    - Price efficiency & slippage
        - Execution price & midprice
        - Trade impact
    - Timing analysis
        - Intertrade time intervals
    - Quote quality
        - Quote to trade ratio
        - How often market moves toward you
        - Are you frequently stale?
    - Us vs bots
        - How do our trades compare with market trades?
2. Holding & inventory metrics
    - Holding time distribution & mean
    - Position management
        - Inventory turnover
        - Position concentration
    - PNL volatility & variance
    - Inventory risk (market maker)
3. PNL analysis
    - Cumulative & periodic PNL
        - Cumulative PNL curve (plot)
        - PNL per product (plot)
    - Trade profitability
        - Average profit per trade
        - Win/loss ratio (profitable vs losing trades)
        - Risk-adjusted returns
4. Orderbook & market microstructure
    - Liquidity & depth
        - Bid ask spread vs time plot
        - Orderbook width & depth (volume of top three levels)
        - Volatility (bid and ask prices & volume volatility)
    - Imbalance metrics
        - Order flow imbalance (bid vs ask volumes)
        - Midprice stability (variance or sdv of midprice over time)
    - Bots logic NOTE
        - Can we identify the logic of the bots?
        - Can we identify if there is a big market maker?
5. Statistical analysis
    - Correlation & regression
    - Correlation matrix
    - Histograms
    - Outlier analysis
"""

########################################################################
# Parse Data
########################################################################

def parse_multiple_json(s):
    """Parse multiple JSON objects from a string using raw_decode"""
    decoder = JSONDecoder()
    pos = 0
    results = []
    s = s.strip()
    while pos < len(s):
        try:
            obj, index = decoder.raw_decode(s, pos)
            results.append(obj)
            pos = index
            # skip any whitespace between objects
            while pos < len(s) and s[pos].isspace():
                pos += 1
        except json.JSONDecodeError:
            break
    return results

# Prepare containers for each section
sandbox_content = []
activities_lines = []
trade_history_lines = []
activities_header = None
current_section = None

with open(f"results/round-0/sample.log", 'r') as f:
    for line in f:
        line_strip = line.strip()
        if not line_strip:
            continue

        # Switch sections based on header lines
        if line_strip.startswith("Sandbox logs:"):
            current_section = "sandbox"
            continue
        elif line_strip.startswith("Activities log:"):
            current_section = "activities"
            continue
        elif line_strip.startswith("Trade History:"):
            current_section = "trade"
            continue

        if current_section == "sandbox":
            sandbox_content.append(line)
        elif current_section == "activities":
            if activities_header is None:  # first nonempty line is header
                activities_header = line_strip.split(';')
            else:
                activities_lines.append(line_strip.split(';'))
        elif current_section == "trade":
            trade_history_lines.append(line_strip)

# Process sandbox logs by joining all lines into one string
sandbox_text = "\n".join(sandbox_content)
sandbox_json_objects = parse_multiple_json(sandbox_text)

########################################################################
# Process Trading States
########################################################################

trading_states = []

for entry in sandbox_json_objects:
    entry.pop("sandboxLog", None)  # remove because it's empty
    if "lambdaLog" in entry:
        lambda_log_str = entry["lambdaLog"].strip()
        if not lambda_log_str:
            continue
        try:
            lambda_log = json.loads(lambda_log_str)
        except json.JSONDecodeError as e:
            print("Error parsing lambdaLog:", e)
            continue

        # Build listings
        listings = {}
        for sym, data in lambda_log.get("listings", {}).items():
            listings[sym] = Listing(symbol=data["symbol"],
                                    product=data["product"],
                                    denomination=data["denomination"])

        # Build order_depths with proper type conversion for keys and values
        order_depths = {}
        for sym, orders in lambda_log.get("order_depths", {}).items():
            od = OrderDepth()
            od.buy_orders = {int(k): int(v) for k, v in orders.get("buy_orders", {}).items()}
            od.sell_orders = {int(k): int(v) for k, v in orders.get("sell_orders", {}).items()}
            order_depths[sym] = od

        # Build market_trades (list of Trade objects) with int conversions
        market_trades = {}
        for sym, trades in lambda_log.get("market_trades", {}).items():
            market_trades[sym] = []
            for t in trades:
                if t.get("timestamp", 0) == lambda_log.get("timestamp", 0) - 100:
                    market_trades[sym].append(
                        Trade(symbol=t["symbol"],
                              price=int(t["price"]),
                              quantity=int(t["quantity"]),
                              buyer=t.get("buyer"),
                              seller=t.get("seller"),
                              timestamp=int(t.get("timestamp", 0)))
                    )

        # Build own_trades with proper int conversion
        own_trades = {}
        for sym, trades in lambda_log.get("own_trades", {}).items():
            own_trades[sym] = []
            for t in trades:
                own_trades[sym].append(
                    Trade(symbol=t["symbol"],
                          price=int(t["price"]),
                          quantity=int(t["quantity"]),
                          buyer=t.get("buyer"),
                          seller=t.get("seller"),
                          timestamp=int(t.get("timestamp", 0)))
                )

        # Position: Ensure that each position value is an int
        position_raw = lambda_log.get("position", {})
        position = {prod: int(val) for prod, val in position_raw.items()}

        # Build observations
        obs_data = lambda_log.get("observations", {})
        plain_obs_raw = obs_data.get("plainValueObservations", {})
        plain_obs = {prod: int(val) for prod, val in plain_obs_raw.items()}
        conv_obs_raw = obs_data.get("conversionObservations", {})
        conv_obs = {}
        for prod, details in conv_obs_raw.items():
            conv_obs[prod] = ConversionObservation(
                bidPrice=float(details.get("bidPrice", 0.0)),
                askPrice=float(details.get("askPrice", 0.0)),
                transportFees=float(details.get("transportFees", 0.0)),
                exportTariff=float(details.get("exportTariff", 0.0)),
                importTariff=float(details.get("importTariff", 0.0)),
                sugarPrice=float(details.get("sugarPrice", 0.0)),
                sunlightIndex=float(details.get("sunlightIndex", 0.0))
            )
        observations = Observation(plainValueObservations=plain_obs,
                                   conversionObservations=conv_obs)

        # Create the TradingState object with types properly set
        state = TradingState(
            traderData=str(lambda_log.get("traderData", "")),
            timestamp=int(lambda_log.get("timestamp", 0)),
            listings=listings,
            order_depths=order_depths,
            own_trades=own_trades,
            market_trades=market_trades,
            position=position,
            observations=observations
        )
        trading_states.append(state)


########################################################################
# Process Activity Logs
########################################################################

activities_df = pd.DataFrame(activities_lines, columns=activities_header)
activities_df.drop(columns=['day'], inplace=True)

# Rename profit_and_loss to pnl and adjust bid/ask volume column names
activities_df.rename(columns={
    'profit_and_loss': 'pnl',
    'bid_volume_1': 'bid_vol_1',
    'bid_volume_2': 'bid_vol_2',
    'bid_volume_3': 'bid_vol_3',
    'ask_volume_1': 'ask_vol_1',
    'ask_volume_2': 'ask_vol_2',
    'ask_volume_3': 'ask_vol_3'
}, inplace=True)

# Split by product and drop the redundant 'product' column from each DataFrame
product_dfs = {
    product: activities_df[activities_df['product'] == product]
                .drop(columns=['product'])
                .reset_index(drop=True)
    for product in activities_df['product'].unique()
}

########################################################################
# Process Trade History
########################################################################

trade_product_dfs = {}
trade_df = pd.DataFrame()  # initialize in case no valid trade history is parsed

if trade_history_lines:
    trade_history_text = " ".join(trade_history_lines)
    try:
        trades_data = json.loads(trade_history_text)
        trade_df = pd.DataFrame(trades_data)
        trade_df = trade_df[['symbol', 'price', 'quantity', 'timestamp']]
        # Create a separate DataFrame for each product (grouped by symbol)
        trade_product_dfs = {
            symbol: trade_df[trade_df['symbol'] == symbol]
                        .drop(columns=['symbol'])
                        .reset_index(drop=True)
            for symbol in trade_df['symbol'].unique()
        }
    except json.JSONDecodeError as e:
        print("Error parsing trade history:", e)

########################################################################
# Analysis and Plotting Functions
########################################################################

def plot_cumulative_pnl(product, df):
    """Plot cumulative PNL for a given product using the activities log."""
    df = df.copy()
    df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
    df['pnl'] = pd.to_numeric(df['pnl'], errors='coerce')
    df.sort_values('timestamp', inplace=True)
    df['cumulative_pnl'] = df['pnl'].cumsum()
    plt.figure()
    plt.plot(df['timestamp'], df['cumulative_pnl'], marker='o', markersize=3)
    plt.title(f'Cumulative PNL for {product}')
    plt.xlabel('Timestamp')
    plt.ylabel('Cumulative PNL')
    plt.grid(True)
    plt.tight_layout()
    file_path = os.path.join("plots", f"cumulative_pnl_{product}.png")
    plt.savefig(file_path)
    plt.close()
    print(f"Cumulative PNL plot saved for {product} at {file_path}")

def plot_bid_ask_spread(product, df):
    """Plot bid-ask spread vs. time for a given product."""
    df = df.copy()
    df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
    df['bid_price_1'] = pd.to_numeric(df['bid_price_1'], errors='coerce')
    df['ask_price_1'] = pd.to_numeric(df['ask_price_1'], errors='coerce')
    df.sort_values('timestamp', inplace=True)
    df['spread'] = df['ask_price_1'] - df['bid_price_1']
    plt.figure()
    plt.plot(df['timestamp'], df['spread'], marker='x', linestyle='--')
    plt.title(f'Bid-Ask Spread for {product}')
    plt.xlabel('Timestamp')
    plt.ylabel('Spread')
    plt.grid(True)
    plt.tight_layout()
    file_path = os.path.join("plots", f"bid_ask_spread_{product}.png")
    plt.savefig(file_path)
    plt.close()
    print(f"Bid-Ask Spread plot saved for {product} at {file_path}")

def plot_intertrade_intervals(symbol, df):
    """Plot histogram of intertrade time intervals for a given symbol."""
    df = df.copy()
    df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
    df.sort_values('timestamp', inplace=True)
    if len(df) < 2:
        print(f"Not enough trades for {symbol} to compute intertrade intervals.")
        return
    intervals = df['timestamp'].diff().dropna()
    plt.figure()
    plt.hist(intervals, bins=10)
    plt.title(f'Intertrade Time Intervals for {symbol}')
    plt.xlabel('Time Interval')
    plt.ylabel('Frequency')
    plt.grid(True)
    plt.tight_layout()
    file_path = os.path.join("plots", f"intertrade_intervals_{symbol}.png")
    plt.savefig(file_path)
    plt.close()
    print(f"Intertrade intervals histogram saved for {symbol} at {file_path}")

def plot_trade_statistics(trade_stats):
    """Plot trade count, average trade size, and variance per symbol as bar charts."""
    symbols = list(trade_stats.keys())
    counts = [trade_stats[s]['count'] for s in symbols]
    avg_sizes = [trade_stats[s]['avg_size'] for s in symbols]
    var_sizes = [trade_stats[s]['var_size'] for s in symbols]

    # Bar chart for trade count
    plt.figure()
    plt.bar(symbols, counts)
    plt.title("Trade Count per Symbol")
    plt.xlabel("Symbol")
    plt.ylabel("Trade Count")
    plt.tight_layout()
    file_path = os.path.join("plots", "trade_count.png")
    plt.savefig(file_path)
    plt.close()
    print(f"Trade count plot saved at {file_path}")

    # Bar chart for average trade size
    plt.figure()
    plt.bar(symbols, avg_sizes)
    plt.title("Average Trade Size per Symbol")
    plt.xlabel("Symbol")
    plt.ylabel("Average Trade Size")
    plt.tight_layout()
    file_path = os.path.join("plots", "avg_trade_size.png")
    plt.savefig(file_path)
    plt.close()
    print(f"Average trade size plot saved at {file_path}")

    # Bar chart for trade size variance
    plt.figure()
    plt.bar(symbols, var_sizes)
    plt.title("Trade Size Variance per Symbol")
    plt.xlabel("Symbol")
    plt.ylabel("Variance")
    plt.tight_layout()
    file_path = os.path.join("plots", "trade_size_variance.png")
    plt.savefig(file_path)
    plt.close()
    print(f"Trade size variance plot saved at {file_path}")

########################################################################
# main()
########################################################################

if __name__ == "__main__":
    
    if PRINT_TRADING_STATES:
        print("\n\n============================================================================================================\n")
        print("Trading States\n")
        for state in trading_states[:3]:
            print(state.toJSON())
            print()
            
    if PRINT_ACTIVITY_LOGS:
        print("\n============================================================================================================\n")
        print("Activity DataFrames")
        for product, df in product_dfs.items():
            print("\n------------------------------------------------------------------------------------------------------------\n")
            print(f"{product}:\n")
            print(df.head(10))

    if PRINT_TRADE_HISTORY:
        print("\n\n============================================================================================================\n")
        print("Trade History DataFrames")
        for symbol, df in trade_product_dfs.items():
            print("\n------------------------------------------------------------------------------------------------------------\n")
            print(f"{symbol}\n")
            print(df.head(10), "\n")
    
    # Create plots folder if it doesn't exist
    if not os.path.exists("plots"):
         os.makedirs("plots")
         print("Created 'plots' directory.")

    # Analysis and plotting
    print("\n============================================================================================================\n")
    print("Performing Analysis and Plotting:")

    # Plot cumulative PNL and bid-ask spread for each product (from activity logs)
    for product, df in product_dfs.items():
         # Ensure numeric types for plotting
         df['pnl'] = pd.to_numeric(df['pnl'], errors='coerce')
         df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
         plot_cumulative_pnl(product, df)
         plot_bid_ask_spread(product, df)
    
    # Compute and print trade statistics from trade history; plot intertrade intervals and summary stats
    trade_stats = {}
    if not trade_df.empty:
         for symbol in trade_df['symbol'].unique():
              symbol_df = trade_df[trade_df['symbol'] == symbol]
              count = len(symbol_df)
              avg_size = symbol_df['quantity'].mean()
              var_size = symbol_df['quantity'].var()
              trade_stats[symbol] = {
                  'count': count,
                  'avg_size': avg_size,
                  'var_size': var_size
              }
              print(f"\nTrade Statistics for {symbol}:")
              print(f"  Total trades: {count}")
              print(f"  Average trade size: {avg_size}")
              print(f"  Trade size variance: {var_size}")
              plot_intertrade_intervals(symbol, symbol_df)
         # Plot aggregated trade statistics
         plot_trade_statistics(trade_stats)
    else:
         print("No trade history data available for analysis.")

    print("\nAnalysis and plotting completed.")
