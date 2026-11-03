def string_sequence(n: int) -> str:
    """
    Return a string containing space-delimited even numbers starting from 0 up to n inclusive.
    >>> string_sequence(0)
    '0'
    >>> string_sequence(5)
    '0 2 4'
    """
    if n < 0:
        raise ValueError("Input must be a non-negative integer")
    
    result = []
    for i in range(n + 1):
        if i % 2 == 0:
            result.append(str(i))
    
    return ' '.join(result).rstrip()
