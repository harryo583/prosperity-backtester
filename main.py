import pandas as pd
import sys
from typing import List, Dict
from datamodel import TradingState, Order
from extractor import trading_states
from typing import Any, Optional
from pathlib import Path
from importlib import import_module, metadata, reload

def parse_algorithm(algo_path: str) -> Any:
    algorithm_path = Path(algo_path).expanduser().resolve()
    if not algorithm_path.is_file():
        raise ModuleNotFoundError(f"{algorithm_path} is not a file")
    
    sys.path.append(str(algorithm_path.parent))
    return import_module(algorithm_path.stem)

def main() -> None:
    algo_path = "algorithms/algo.py"
    trader_module = parse_algorithm(algo_path)
    trader = trader_module.Trader
    pass

if __name__ == "__main__":
    main()