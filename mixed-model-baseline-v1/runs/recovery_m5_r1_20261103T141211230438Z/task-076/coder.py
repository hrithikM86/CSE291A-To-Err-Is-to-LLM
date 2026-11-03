def is_simple_power(x: int, n: int) -> bool:
    if x == 0 or n == 0:
        return False
    if n == 1:
        return x == 1
    if x == 1 and n > 1:
        return False
    if x == 0 and n == 1:
        return False
    
    k = 1
    while n**k < x:
        k += 1
    return n**k == x
