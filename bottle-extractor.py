# bottle-extractor.py

import json
import pandas as pd
from datamodel import TradingState, Listing, OrderDepth, Trade, Observation, ConversionObservation

PRINT_TRADING_STATES = False
ROUND_NUMBER = 5
DAY_NUMBER = 0

########################################################################
# Read CSV Files
########################################################################

# Read the prices and trades CSV files (using semicolon as delimiter)
prices_df = pd.read_csv(f"raw/round-{ROUND_NUMBER}/day-{DAY_NUMBER}/prices.csv", delimiter=";")
trades_df = pd.read_csv(f"raw/round-{ROUND_NUMBER}/day-{DAY_NUMBER}/trades.csv", delimiter=";")

########################################################################
# Process Trading States from CSV files
########################################################################

trading_states = []

# Group the prices by timestamp
for timestamp, group in prices_df.groupby("timestamp"):
    listings = {}
    order_depths = {}
    position = {}
    plain_obs = {}

    # Process each row (each product snapshot) for this timestamp
    for idx, row in group.iterrows():
        product = row["product"]

        # Build a Listing (using empty string for denomination)
        if product not in listings:
            listings[product] = Listing(symbol=product, product=product, denomination="")

        # Build the OrderDepth from the bid/ask levels
        od = OrderDepth()
        # Process bid orders (up to three levels)
        for i in [1, 2, 3]:
            bid_price_col = f"bid_price_{i}"
            bid_vol_col = f"bid_volume_{i}"
            bid_price_val = row[bid_price_col]
            bid_vol_val = row[bid_vol_col]
            if pd.notna(bid_price_val) and bid_price_val != "":
                try:
                    price_int = int(float(bid_price_val))
                    volume_int = int(float(bid_vol_val)) if pd.notna(bid_vol_val) and bid_vol_val != "" else 0
                    od.buy_orders[price_int] = volume_int
                except Exception as e:
                    pass
        # Process ask orders (up to three levels)
        for i in [1, 2, 3]:
            ask_price_col = f"ask_price_{i}"
            ask_vol_col = f"ask_volume_{i}"
            ask_price_val = row[ask_price_col]
            ask_vol_val = row[ask_vol_col]
            if pd.notna(ask_price_val) and ask_price_val != "":
                try:
                    price_int = int(float(ask_price_val))
                    volume_int = int(float(ask_vol_val)) if pd.notna(ask_vol_val) and ask_vol_val != "" else 0
                    od.sell_orders[price_int] = -volume_int # NOTE
                except Exception as e:
                    pass
        order_depths[product] = od

        # For this CSV we set a default position (could later be updated if needed)
        position[product] = 0

        # Use the mid_price as a plain observation for the product
        try:
            mid_price_val = float(row["mid_price"])
        except Exception:
            mid_price_val = 0.0
        plain_obs[product] = mid_price_val

    # Create the observation object (no conversion observations available from CSV)
    observations = Observation(plainValueObservations=plain_obs, conversionObservations={})

    # Build market trades for each product for this trading state.
    state_market_trades = {}
    for product in listings.keys():
        ts_filter = int(timestamp) - 100
        trades_subset = trades_df[(trades_df["timestamp"] == ts_filter) &
                                  (trades_df["symbol"] == product)]
        trades_list = []
        for _, trade_row in trades_subset.iterrows():
            try:
                price_val = int(float(trade_row["price"]))
                qty_val = int(trade_row["quantity"])
            except Exception:
                price_val = 0
                qty_val = 0
            trade_obj = Trade(
                symbol=trade_row["symbol"],
                price=price_val,
                quantity=qty_val,
                buyer=trade_row["buyer"] if pd.notna(trade_row["buyer"]) and trade_row["buyer"] != "" else None,
                seller=trade_row["seller"] if pd.notna(trade_row["seller"]) and trade_row["seller"] != "" else None,
                timestamp=int(trade_row["timestamp"])
            )
            trades_list.append(trade_obj)
        state_market_trades[product] = trades_list

    # Create the TradingState object for this timestamp
    state = TradingState(
        traderData="",
        timestamp=int(timestamp),
        listings=listings,
        order_depths=order_depths,
        own_trades={},  # no own trades provided in the CSV files
        market_trades=state_market_trades,
        position=position,
        observations=observations
    )
    trading_states.append(state)

########################################################################
# Write Trading States to JSON File
########################################################################

# Convert each TradingState into a dictionary and then dump to file.
trading_states_list = [json.loads(state.toJSON()) for state in trading_states]
with open(f"data/round-{ROUND_NUMBER}/day-{DAY_NUMBER}/trading_states.json", "w") as ts_file:
    json.dump(trading_states_list, ts_file, indent=2)

########################################################################
# Optionally print Trading States to Console
########################################################################

if PRINT_TRADING_STATES:
    print("\n\n============================================================================================================\n")
    print("Trading States\n")
    for state in trading_states:
        print(state.toJSON())
        print()
