def choose_num(x: int, y: int) -> int:
    """
    This function takes two positive numbers x and y and returns the
    biggest even integer number that is in the range [x, y] inclusive. If 
    there's no such number, then the function should return -1.
    """
    # Input validation
    if not (isinstance(x, int) and isinstance(y, int) and x > 0 and y > 0):
        raise ValueError("Both x and y must be positive integers.")
    if x > y:
        return -1

    # Finding the largest even number
    if y % 2 == 0:
        return y
    elif y - 1 >= x and (y - 1) % 2 == 0:
        return y - 1
    else:
        return -1
