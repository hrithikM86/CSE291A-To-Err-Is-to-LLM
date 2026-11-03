def digits(n: int) -> int:
    if n <= 0:
        return 0
    
    product = 1
    seen = set()
    
    while n > 0:
        digit = n % 10
        if digit % 2 != 0 and digit not in seen:
            product *= digit
            seen.add(digit)
        n //= 10
    
    return product if product != 1 else 0
