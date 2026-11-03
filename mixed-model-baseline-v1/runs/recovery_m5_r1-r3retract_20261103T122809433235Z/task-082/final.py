def is_prime(n: int) -> bool:
    if n <= 1:
        return False
    if n in [2, 3]:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def prime_length(string: str) -> bool:
    if not string:
        return False
    length = len(string)
    return is_prime(length)
