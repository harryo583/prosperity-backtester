# prosperity-backtester

## Files & Directories

### main.py: runs the trading algorithms, matching it against resting orders and past trades
### driller.py: defines a placeholder algorithm for drilling market data from the official sandbox
### extractor.py: parses data from the official logs of driller.py
### matcher.py: order matching engine; defines utilities that facilitate order matching
### data/: where each round's drilled data is stored
### results/: backtesting results (an orderbook csv, a pnl vs time plot, a trade history csv)
### algorithms/: where to store your algorithms to backtest