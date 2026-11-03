def generate_integers(a: int, b: int) -> list:
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
