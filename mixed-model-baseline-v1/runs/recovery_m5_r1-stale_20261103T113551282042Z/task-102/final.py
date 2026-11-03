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

    # Finding the largest even number in the range [x, y]
    if y % 2 == 0:
        largest_even = y
    else:
        largest_even = y - 1

    # Check if the largest even number is within the range [x, y]
    if largest_even >= x:
        return largest_even
    else:
        return -1
