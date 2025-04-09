
from itertools import product
import subprocess


'''
add a parameter reader to the top of your algo.py file

parameters_path = PARAMETER_PATH
with open(parameters_path, 'r') as f:
    line = f.readline().strip()
    if line:
        P1, P2, P3, P4 = line.split(',')

        P1 = float(alpha_str)
        P2 = int(fast_span_str)
        P3 = int(slow_span_str)
        P4 = float(diff_val_str)
'''

class GridSearcher:

    def __init__(self):
        self.parameters = []

    def add_parameter(self, name, begin, end, increment):
        self.parameters.append({
            'name': name,
            'begin': begin,
            'end': end,
            'increment': increment
        })

    def grid_search(self,algo_path):
        # go through all combinations of parameters
        param_values = []
        for param in self.parameters:
            values = []
            current = param['begin']
            while current <= param['end']:
                values.append(current)
                current += param['increment']
            param_values.append(values)
        all_combinations = list(product(*param_values))
        
        best_pnl = float('-inf')
        best_combination = None

        
        for combination in all_combinations:
            total_pnl = 0
            line = ','.join(str(v) for v in combination)
            with open('grid_search_data/parameters.txt', 'w') as f:
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

        with open('grid_search_data/parameters.txt', 'w') as f:
            f.write('')
        with open('grid_search_data/pnl.txt', 'w') as f:
            f.write('')
        
        

        



