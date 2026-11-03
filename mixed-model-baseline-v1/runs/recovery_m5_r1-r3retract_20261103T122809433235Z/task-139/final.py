from math import factorial

def special_factorial(n: int) -> int:
    if not isinstance(n, int) or n <= 0:
        raise ValueError("Input must be a positive integer.")
    
    if n == 1:
        return 1
    
    result = 1
    for i in range(1, n + 1):
        result *= factorial(i)
    
    return result
