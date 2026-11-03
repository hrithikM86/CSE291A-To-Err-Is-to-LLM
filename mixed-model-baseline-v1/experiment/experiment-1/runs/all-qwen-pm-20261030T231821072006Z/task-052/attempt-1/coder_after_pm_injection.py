def below_threshold(l: list, t: int) -> bool:
    """
    Return True if all numbers in the list l are below threshold t.
    """
    # Input validation
    if not isinstance(l, list) or not isinstance(t, int):
        raise TypeError("l must be a list and t must be an integer")
    
    # Edge case handling
    if not l:
        return True
    
    # Main logic
    for num in l:
        if num >= t:
            return False
    
    # Final return
    return True
