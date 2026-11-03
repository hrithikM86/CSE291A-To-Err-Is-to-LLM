def is_equal_to_sum_even(n: int) -> bool:
    """
    Evaluate whether the given number n can be written as the sum of exactly 4 positive even numbers
    """
    # Input Validation
    if n < 1 or n > 10000:
        return False
    
    # Edge Cases
    if n < 8 or n % 2 != 0:
        return False
    
    # General Case
    return n % 4 == 0
