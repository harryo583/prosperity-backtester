import pandas as pd
from typing import List, Dict
from datamodel import TradingState, Order
from extractor import trading_states
from ..rounds.tutorial.algo import Trader

class Backtester:
    def __init__(self, trading_states: List[TradingState], trader: Trader):
        self.trading_states = trading_states
        self.trader = trader
        self.position_history = []
        self.pnl_history = []
        self.orders_history = []

        # Initialize your simulated position and cash.
        self.positions = {} # key: product, value: current position
        self.cash = 0.0 # assume starting with 0 cash
        self.last_state = None

    def simulate_fill(self, order: Order, state: TradingState) -> int:
        """
        Simplified fill simulation:
        For example, assume your order is fully filled at the mid price.
        You could improve this by using state.order_depths or historical trades.
        Returns the filled quantity (could be partial fill).
        """
        # Here, we simply return the order quantity as filled.
        return order.quantity

    def update_pnl(self, product: str, order: Order, fill_qty: int, state: TradingState):
        """
        Update cash and positions based on the filled order.
        For simplicity, assume order is filled at a theoretical price.
        """
        # In a more sophisticated simulation, you might extract a mid-price from state.
        mid_price = state.observations.plainValueObservations.get(product, 0)  # placeholder
        # For BUY orders, cash decreases and position increases; for SELL, vice versa.
        if order.quantity > 0:
            self.cash -= mid_price * fill_qty
            self.positions[product] = self.positions.get(product, 0) + fill_qty
        else:
            self.cash += mid_price * fill_qty
            self.positions[product] = self.positions.get(product, 0) - fill_qty

    def run_backtest(self):
        for state in self.trading_states:
            # Save the state for record keeping
            self.last_state = state

            # Get orders from your strategy
            orders_result = self.trader.run(state)
            # Depending on your implementation, run() might return (orders, conversions, traderData)
            if isinstance(orders_result, tuple):
                orders, conversions, traderData = orders_result
            else:
                orders = orders_result

            self.orders_history.append(orders)
            # Process orders for each product
            for product, orders_list in orders.items():
                for order in orders_list:
                    # Simulate fill for each order.
                    fill_qty = self.simulate_fill(order, state)
                    # Update positions and cash
                    self.update_pnl(product, order, fill_qty, state)

            # Record the current positions and pnl
            self.position_history.append(self.positions.copy())
            # Calculate a simple pnl: cash plus market value of positions (using a placeholder price)
            pnl = self.cash
            for product, pos in self.positions.items():
                price = state.observations.plainValueObservations.get(product, 0)
                pnl += price * pos
            self.pnl_history.append(pnl)

        # At the end, you can compile results into DataFrames
        results = pd.DataFrame({
            'position': self.position_history,
            'pnl': self.pnl_history
        })
        return results

# Example usage:
if __name__ == "__main__":
    # Suppose you already loaded trading_states from your logs file.
    trader = Trader()
    backtester = Backtester(trading_states, trader)
    results_df = backtester.run_backtest()
    print("Backtest Results:")
    print(results_df)