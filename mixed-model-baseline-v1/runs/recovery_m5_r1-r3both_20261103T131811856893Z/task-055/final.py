def fib(n: int) -> int:
    """
    Return n-th Fibonacci number.
    >>> fib(10)
    55
    >>> fib(1)
    1
    >>> fib(8)
    21
    """
    if n < 1:
        raise ValueError("Input must be a positive integer.")
    if n == 1 or n == 2:
        return 1
    # Memoization dictionary to store previously computed values
    memo = {1: 1, 2: 1}
    return _fib(n, memo)

def _fib(n: int, memo: dict) -> int:
    if n not in memo:
        memo[n] = _fib(n-1, memo) + _fib(n-2, memo)
    return memo[n]
