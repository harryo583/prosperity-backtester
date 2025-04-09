import importlib.util
import sys

algo_path = "algorithms/5k.py"
module_name = "algo_trader_5k"  # can be any unique name

# Load the module from the file
spec = importlib.util.spec_from_file_location(module_name, algo_path)
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module
spec.loader.exec_module(module)
Trader = module.Trader

trader = Trader()

params = {}