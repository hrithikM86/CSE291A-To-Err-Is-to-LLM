def prime_fib(n: int) -> int:
    def is_prime(num: int) -> bool:
        if num <= 1:
            return False
        if num <= 3:
            return True
        if num % 2 == 0 or num % 3 == 0:
            return False
        i = 5
        while i * i <= num:
            if num % i == 0 or num % (i + 2) == 0:
                return False
            i += 6
        return True

    if not isinstance(n, int):
        raise ValueError("Input must be an integer.")
    if n < 1:
        raise ValueError("Input must be greater than 0.")
    if n > 20:
        raise ValueError("Input must be less than or equal to 20.")

    fibonacci = []
    a, b = 0, 1
    count = 0

    while count < n:
        next_fib = a + b
        if is_prime(next_fib):
            fibonacci.append(next_fib)
            count += 1
        a, b = b, next_fib

    return fibonacci[-1]
