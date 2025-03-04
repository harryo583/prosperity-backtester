# matcher.py

import pandas as pd
from typing import List, Dict
from datamodel import TradingState, Order, Symbol, Trade

def match_buy_order(state: TradingState, next_state: TradingState, order: Order) -> List[Trade]:
    trades = []
    market_trades = next_state.market_trades if next_state else None
    remaining_quantity = order.quantity
    order_depth = state.order_depths.get(order.symbol)
    
    # First fill with order depth
    if order_depth and order_depth.sell_orders:
        eligible_prices = sorted([price for price in order_depth.sell_orders.keys() if price <= order.price])
        
        for price in eligible_prices:
            available = order_depth.sell_orders[price]
            if available <= 0:
                continue
            matched_quantity = min(remaining_quantity, available)
            trades.append(
                Trade(
                    symbol = order.symbol,
                    price = price,
                    quantity = matched_quantity,
                    buyer = "SUBMISSION",
                    seller = "",
                    timestamp = state.timestamp
                )
            )
            order_depth.sell_orders[price] -= matched_quantity
            remaining_quantity -= matched_quantity
            if remaining_quantity == 0:
                return trades
    print(remaining_quantity)
    print("Trades:", trades)
    # Fill any remaining quantity with market trades
    if remaining_quantity > 0 and market_trades and order.symbol in market_trades:
        for market_trade in market_trades[order.symbol]:
            if remaining_quantity <= 0:
                break
            if market_trade.quantity <= 0:
                continue
            # if market_trade.timestamp != next_state.timestamp: # make sure market trade is recent
            #     continue
            if order.price >= market_trade.price: # only match if you're willing to pay higher
                matched_quantity = min(remaining_quantity, market_trade.quantity)
                trades.append(
                    Trade(
                        symbol = order.symbol,
                        price = order.price,
                        quantity = matched_quantity,
                        buyer = "SUBMISSION",
                        seller = "",
                        timestamp = state.timestamp
                    )
                )
                market_trade.quantity -= matched_quantity
                remaining_quantity -= matched_quantity
    print("Trades:", trades)
    return trades

def match_sell_order(state: TradingState, next_state: TradingState, order: Order) -> List[Trade]:
    trades = []
    market_trades = next_state.market_trades if next_state else None
    remaining_quantity = abs(order.quantity) # sell order quantities are negative by convetion
    order_depth = state.order_depths.get(order.symbol)
    
    # print(order_depth.buy_orders)
    
    # First fill with order depth
    if order_depth and order_depth.buy_orders:
        eligible_prices = sorted([price for price in order_depth.buy_orders.keys() if price >= order.price], reverse=True)
        for price in eligible_prices:
            available = order_depth.buy_orders[price]
            if available <= 0:
                continue
            matched_quantity = min(remaining_quantity, available)
            trades.append(
                Trade(
                    symbol = order.symbol,
                    price = price,
                    quantity = matched_quantity,
                    buyer = "",
                    seller = "SUBMISSION",
                    timestamp = state.timestamp
                )
            )
            order_depth.buy_orders[price] -= matched_quantity
            remaining_quantity -= matched_quantity
            if remaining_quantity == 0:
                return trades
    # print(remaining_quantity)
    # print("HEY", market_trades)
    # Fill any remaining quantity with market trades
    if remaining_quantity > 0 and market_trades and order.symbol in market_trades:
        for market_trade in market_trades[order.symbol]:
            if remaining_quantity <= 0:
                break
            if market_trade.quantity <= 0:
                continue
            # if market_trade.timestamp != next_state.timestamp: # make sure market trade is recent
            #     continue
            if order.price <= market_trade.price: # only match if you're willing to accept lower
                matched_quantity = min(remaining_quantity, market_trade.quantity)
                trades.append(
                    Trade(
                        symbol = order.symbol,
                        price = order.price,
                        quantity = matched_quantity,
                        buyer = "",
                        seller = "SUBMISSION",
                        timestamp = state.timestamp
                    )
                )
                market_trade.quantity -= matched_quantity
                remaining_quantity -= matched_quantity
    return trades