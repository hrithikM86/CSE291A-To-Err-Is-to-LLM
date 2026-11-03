import math

def is_prime(n: int) -> bool:
    if n <= 1:
        return False
    for i in range(2, int(math.sqrt(n)) + 1):
        if n % i == 0:
            return False
    return True

def is_multiply_prime(a: int) -> bool:
    if a < 2:
        return False
    
    prime_factors = set()
    for i in range(2, int(math.sqrt(a)) + 1):
        if a % i == 0 and is_prime(i):
            prime_factors.add(i)
            while a % i == 0:
                a //= i
    if a > 1 and is_prime(a):
        prime_factors.add(a)
    
    return len(prime_factors) == 3

# Test cases
print(is_multiply_prime(30))  # True, 30 = 2 * 3 * 5
print(is_multiply_prime(60))  # True, 60 = 2 * 3 * 5
print(is_multiply_prime(8))   # False, 8 = 2 * 2 * 2
print(is_multiply_prime(10))  # False, 10 = 2 * 5
print(is_multiply_prime(2 * 2 * 2 * 3 * 3))  # False, 72 = 2 * 2 * 2 * 3 * 3
