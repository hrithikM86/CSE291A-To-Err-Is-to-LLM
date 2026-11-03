def string_sequence(n: int) -> str:
    """
    Return a string containing space-delimited numbers starting from 0 up to n inclusive.
    >>> string_sequence(0)
    '0'
    >>> string_sequence(5)
    '0 1 2 3 4 5'
    """
    if not isinstance(n, int) or n < 0:
        raise ValueError("Input must be a non-negative integer")

    if n == 0:
        return '0'

    result = ''
    for i in range(n + 1):
        result += str(i) + ' '

    return result.strip()
