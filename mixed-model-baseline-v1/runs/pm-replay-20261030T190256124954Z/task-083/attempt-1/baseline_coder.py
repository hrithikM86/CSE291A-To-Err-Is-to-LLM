def starts_one_ends(n: int) -> int:
    if n < 1:
        raise ValueError("Input must be a positive integer.")
    
    if n == 1:
        return 1
    
    total_count = 2 * 10**(n-1) - 10**(n-2)
    return total_count
