def greatest_common_divisor(a: int, b: int) -> int:
    """
    Return a greatest common divisor of two integers a and b
    >>> greatest_common_divisor(3, 5)
    1
    >>> greatest_common_divisor(25, 15)
    5
    """
    def _gcd_helper(x: int, y: int) -> int:
        while y:
            x, y = y, x % y
        return abs(x)

    if not isinstance(a, int) or not isinstance(b, int):
        raise TypeError("Both a and b must be integers")

    a, b = abs(a), abs(b)
    if a == 0:
        return b
    if b == 0:
        return a

    gcd_value = _gcd_helper(a, b)
    return gcd_value
