from typing import List
import math

def factorize(n: int) -> List[int]:
    if not isinstance(n, int) or n <= 0:
        raise ValueError("Input must be a positive integer")
    
    factors = []
    # Handle edge cases
    if n == 0:
        return factors
    if n == 1:
        return [1]
    
    # Factorization algorithm
    divisor = 2
    while divisor <= math.sqrt(n):
        if n % divisor == 0:
            factors.append(divisor)
            n //= divisor
        else:
            divisor += 1
    
    if n > 1:
        factors.append(n)
    
    return factors
