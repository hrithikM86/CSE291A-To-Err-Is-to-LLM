def is_equal_to_sum_even(n: int) -> bool:
    """
    Evaluate whether the given number n can be written as the sum of exactly 4 positive even numbers
    """
    # Input Validation
    if not isinstance(n, int) or n < 1 or n > 10000:
        return False

    # Edge Cases
    if n < 8 or n % 2 != 0:
        return False

    # General Case
    if n == 8:
        return True
    elif (n - 8) % 2 == 0 and (n - 8) >= 0:
        return True
    else:
        return False
