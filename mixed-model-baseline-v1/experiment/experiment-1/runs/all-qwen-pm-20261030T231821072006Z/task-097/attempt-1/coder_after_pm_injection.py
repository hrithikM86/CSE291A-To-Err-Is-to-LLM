def multiply(a: int, b: int) -> int:
    a = abs(a)
    b = abs(b)
    
    unit_digit_a = a % 10
    unit_digit_b = b % 10
    
    tens_digit_a = (a // 10) % 10
    tens_digit_b = (b // 10) % 10
    
    return tens_digit_a * tens_digit_b
