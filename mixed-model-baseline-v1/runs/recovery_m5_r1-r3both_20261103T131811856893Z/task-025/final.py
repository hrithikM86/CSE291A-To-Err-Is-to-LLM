from typing import List
import math

def factorize(n: int) -> List[int]:
    """
    Return list of prime factors of given integer in the order from smallest to largest.
    Each of the factors should be listed number of times corresponding to how many times it appeares in factorization.
    Input number should be equal to the product of all factors
    >>> factorize(8)
    [2, 2, 2]
    >>> factorize(25)
    [5, 5]
    >>> factorize(70)
    [2, 5, 7]
    """
    if not isinstance(n, int) or n <= 0:
        raise ValueError("Input must be a positive integer")

    factors = []
    # Check for number of 2s in n
    while n % 2 == 0:
        factors.append(2)
        n //= 2

    # n must be odd at this point, so a skip of 2 (i.e., i = i + 2) can be used
    for i in range(3, int(math.sqrt(n)) + 1, 2):
        # While i divides n, append i and divide n
        while n % i == 0:
            factors.append(i)
            n //= i

    # This condition is to check if n is a prime number greater than 2
    if n > 2:
        factors.append(n)

    return factors
