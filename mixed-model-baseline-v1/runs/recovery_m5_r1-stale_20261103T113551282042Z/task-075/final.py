import math

def is_prime(n):
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

def is_multiply_prime(a: int) -> bool:
    if a < 2:
        return False
    distinct_primes = set()
    for i in range(2, int(math.sqrt(a)) + 1):
        while a % i == 0 and is_prime(i):
            distinct_primes.add(i)
            a //= i
    if a > 1 and is_prime(a):
        distinct_primes.add(a)
    return len(distinct_primes) == 3
