
from itertools import product
import subprocess
import sys


parameters = []
def add_parameter(name, begin, end, increment):
    parameters.append({
        'name': name,
        'begin': begin,
        'end': end,
        'increment': increment
    })

def grid_search(algo_path):
    # go through all combinations of parameters
    param_values = []
    for param in parameters:
        values = []
        current = param['begin']
        while current <= param['end']:
            values.append(current)
            current += param['increment']
        param_values.append(values)
    all_combinations = list(product(*param_values))
    
    best_pnl = float('-inf')
    best_combination = None

    with open('grid_search_data/parameters.txt', 'w') as f:
        for combination in all_combinations:
            total_pnl = 0
            line = ','.join(str(v) for v in combination)
            f.write(line + '\n')
            subprocess.run(['python3', 'main.py', "0", algo_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # wait for it to finish

            with open('grid_search_data/pnl.txt', 'r') as pnl_file:
                pnl = float(pnl_file.readline().strip())
                total_pnl += pnl
            subprocess.run(['python3', 'main.py', "1", algo_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with open('grid_search_data/pnl.txt', 'r') as pnl_file:
                pnl = float(pnl_file.readline().strip())
                total_pnl += pnl
            subprocess.run(['python3', 'main.py', "2", algo_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with open('grid_search_data/pnl.txt', 'r') as pnl_file:
                pnl = float(pnl_file.readline().strip())
                total_pnl += pnl

            print("Current PNL:", total_pnl, "Combination:", combination)
            if total_pnl > best_pnl:
                best_pnl = total_pnl
                best_combination = combination
            
    print("Best PNL:", best_pnl)
    print("Best Combination:", best_combination)

    # clear both files
    with open('grid_search_data/parameters.txt', 'w') as f:
        f.write('')
    with open('grid_search_data/pnl.txt', 'w') as f:
        f.write('')

if __name__ == "__main__":
    algo_path = "/home/zhoujiayi/prosperity-3/prosperity-3/round-0/algo.py"
    add_parameter('ALPHA', 0.01, 0.5, 0.01)
    add_parameter('FAST_SPAN', 5, 50, 5)
    add_parameter('SLOW_SPAN', 50, 200, 10)
    add_parameter('DIFF_VAL', 0.1, 1.0, 0.1)
    grid_search(algo_path)
    

    



