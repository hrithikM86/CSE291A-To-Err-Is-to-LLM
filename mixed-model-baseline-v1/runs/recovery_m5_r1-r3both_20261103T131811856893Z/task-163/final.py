def generate_integers(a: int, b: int) -> list:
    """
    Given two positive integers a and b, return the even digits between a
    and b, in ascending order.

    For example:
    generate_integers(2, 8) => [2, 4, 6, 8]
    generate_integers(8, 2) => [2, 4, 6, 8]
    generate_integers(10, 14) => []
    """
    if not (isinstance(a, int) and isinstance(b, int)):
        raise ValueError("Both a and b must be integers.")
    if a <= 0 or b <= 0:
        raise ValueError("Both a and b must be positive integers.")

    if a > b:
        a, b = b, a

    result = []
    for i in range(a, b + 1):
        for char in str(i):
            if char in '2468':
                result.append(int(char))

    return result
