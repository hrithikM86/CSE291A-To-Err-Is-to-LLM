import math

def is_prime(n: int) -> bool:
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True

def count_prime_factors(n: int) -> int:
    count = 0
    for p in range(2, int(math.sqrt(n)) + 1):
        if is_prime(p):
            while n % p == 0:
                n //= p
                count += 1
                if count > 3:
                    return False
    if n > 1:
        count += 1
    return count

def is_multiply_prime(a: int) -> bool:
    if a < 2 or a >= 100:
        return False
    return count_prime_factors(a) == 3
