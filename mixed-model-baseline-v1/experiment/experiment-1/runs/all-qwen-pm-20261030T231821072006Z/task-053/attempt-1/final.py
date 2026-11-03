def add(x: int, y: int) -> int:
    """
    Add two numbers x and y
    >>> add(2, 3)
    5
    >>> add(5, 7)
    12
    """
    # Input Validation
    if not isinstance(x, int) or not isinstance(y, int):
        raise TypeError("Both x and y must be integers")

    # Edge Cases
    if x == 0:
        return y
    if y == 0:
        return x
    if x == 0 and y == 0:
        return 0

    # Sum Calculation
    # For nonzero x and y, return x + y
    return x + y
