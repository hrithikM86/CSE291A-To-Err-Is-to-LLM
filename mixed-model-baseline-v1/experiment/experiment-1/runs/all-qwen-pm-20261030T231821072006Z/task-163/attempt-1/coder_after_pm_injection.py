def generate_integers(a: int, b: int) -> list:
    """
    Given two positive integers a and b, return the even digits between a
    and b, in ascending order.

    For example:
    generate_integers(2, 8) => [2, 4, 6, 8]
    generate_integers(8, 2) => [2, 4, 6, 8]
    generate_integers(10, 14) => []
    """
    # Ensure a is less than or equal to b
    if a > b:
        a, b = b, a

    result = []
    for num in range(a, b + 1):
        if num > 9 and num % 2 == 0:
            result.append(num)

    return result
