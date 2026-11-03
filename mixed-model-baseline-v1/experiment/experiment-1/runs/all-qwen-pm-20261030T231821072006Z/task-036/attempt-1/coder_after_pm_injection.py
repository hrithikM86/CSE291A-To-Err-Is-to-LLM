def fizz_buzz(n: int) -> int:
    """
    Return the number of times the digit 7 appears in integers less than n which are divisible by 11 or 13.
    >>> fizz_buzz(50)
    0
    >>> fizz_buzz(78)
    2
    >>> fizz_buzz(79)
    3
    """
    if n < 1 or n > 10000:
        raise ValueError("Input must be between 1 and 10000")

    count = 0
    for i in range(1, n):
        if i % 11 == 0 and i % 13 == 0:
            count += str(i).count('7')
    return count
