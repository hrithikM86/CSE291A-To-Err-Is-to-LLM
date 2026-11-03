import math

def sum_squares(lst):
    if not lst:
        return 0
    
    total = 0
    for num in lst:
        ceiled_num = math.ceil(num)
        squared_num = ceiled_num ** 2
        total += squared_num
    
    return total
