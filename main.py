import pandas as pd
import sys
import matplotlib.pyplot as plt
from pathlib import Path
from importlib import import_module
from matcher import match_buy_order, match_sell_order
from datamodel import TradingState, Listing, OrderDepth, Trade, Observation, ConversionObservation
import json

VERBOSE = False
CML_LOG_LENGTH = None
DISPLAY_PNL = False

PRODUCTS = ["RAINFOREST_RESIN", "KELP"]
POSITION_LIMITS = {
    "RAINFOREST_RESIN": 100,
    "KELP": 100
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
    plt.savefig(f"results/round-{round_number}/pnl_over_time.png")
    
    if DISPLAY_PNL:
        plt.show()

def main(algo_path = None) -> None:
    if not algo_path:
        print("No algo path provided, using algorithms/algo.py")
        algo_path = "algorithms/algo.py"
    
    trader_module = parse_algorithm(algo_path)
    
    trader = trader_module.Trader()  # trader instance
    trader.cash = 0  # initial cash
    trader.pnl = 0  # initial pnl
    
    # Containers for exporting CSVs and tracking PnL
    market_conditions = []  # list of dicts for market conditions snapshot
    trade_history_list = []  # list of dicts for each trade
    pnl_over_time = []  # list of (timestamp, pnl)
    
    # Variables to keep track of trader logs
    position = {prod: 0 for prod in PRODUCTS}
    traderData = None

    for i, state in enumerate(trading_states):
        next_state = trading_states[i + 1] if i < len(trading_states) - 1 else None
        timestamp = state.timestamp
        traded = False
        
        if CML_LOG_LENGTH and timestamp > CML_LOG_LENGTH * 100:
            break

        # Update the state with newest trader data
        state.position = position
        state.traderData = traderData  # traderData from previous run
        
        result, conversions, traderData = trader.run(state)
        
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
                    trader.cash -= sum(trade.price * trade.quantity for trade in trades_executed)  # update cash
                elif order.quantity < 0:  # sell order
                    trades_executed = match_sell_order(state, next_state, order)
                    total_filled = sum(trade.quantity for trade in trades_executed)
                    position[product] = position.get(product, 0) - total_filled  # update trader position
                    trader.cash += sum(trade.price * trade.quantity for trade in trades_executed)  # update cash
                
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
                
                if CML_LOG_LENGTH and trades_executed and timestamp < CML_LOG_LENGTH * 100:
                    traded = True
                    print(f"[{timestamp}]")
                    if VERBOSE:
                        print(f"Executed trades for order {order}: {trades_executed}")
                    else:
                        for trade in trades_executed:
                            print_self_trade(trade)
        
        trader.pnl = trader.cash
        for product, pos in position.items():
            mid_price = (max(state.order_depths[product].buy_orders) + min(state.order_depths[product].sell_orders)) / 2
            trader.pnl += pos * mid_price
                    
        if traded and timestamp < CML_LOG_LENGTH * 100:
            print(f"Positions: {state.position}")
            print(f"Cash: {trader.cash}\n")
            print(f"PNL: {trader.pnl}\n")
        
        # Record pnl over time
        pnl_over_time.append((timestamp, trader.pnl))
        
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
    market_conditions_df.to_csv(f"results/round-{round_number}/orderbook.csv", sep=";", index=False)
    
    trade_history_df = pd.DataFrame(trade_history_list)
    trade_history_df = trade_history_df[["timestamp", "buyer", "seller", "symbol", "currency", "price", "quantity"]]
    trade_history_df.to_csv(f"results/round-{round_number}/trade_history.csv", sep=";", index=False)
    
    print("Overall PNL:", trader.pnl)
    print("Exported orderbook.csv and trade_history.csv.")
    
    plot_pnl(pnl_over_time)  # call plotting function

if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print("No round number provided. Defaulting to round-0.")
        round_number = 0
        trading_states = load_trading_states("data/round-0/trading_states.json")
    else:
        round_number = sys.argv[1]
        trading_states = load_trading_states(f"data/round-{round_number}/trading_states.json")
    
    algo_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    main(algo_path)