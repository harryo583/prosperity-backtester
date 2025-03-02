# matcher.py: order matching engine

import pandas as pd
from typing import List, Dict
from datamodel import TradingState, Order, Symbol, Trade

def match_buy_order(state: TradingState, order: Order, market_trades: Dict[Symbol, List[Trade]]) -> List[Trade]:
    trades = []

def match_sell_order(state: TradingState, order: Order, market_trades: Dict[Symbol, List[Trade]]) -> List[Trade]:
    trades = []