def string_sequence(n: int) -> str:
    if not isinstance(n, int) or n < 0:
        raise ValueError("Input must be a non-negative integer")
    
    if n == 0:
        return '0'
    
    result = []
    for i in range(n + 1):
        result.append(str(i))
    
    return ' '.join(result)
