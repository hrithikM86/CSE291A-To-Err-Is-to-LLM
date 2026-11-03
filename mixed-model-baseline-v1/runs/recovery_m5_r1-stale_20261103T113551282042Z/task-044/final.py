def change_base(x: int, base: int) -> str:
    if not 2 <= base <= 9:
        raise ValueError("Base must be between 2 and 9.")
    
    if x == 0:
        return '0'
    
    result = ''
    is_negative = x < 0
    x = abs(x)
    
    while x > 0:
        result += str(x % base)
        x //= base
    
    if is_negative:
        result = '-' + result
    
    return result
