def multiply(a: int, b: int) -> int:
    # Extract unit digits
    unit_digit_a = abs(a % 10)
    unit_digit_b = abs(b % 10)
    
    # Multiply unit digits
    result = unit_digit_a * unit_digit_b
    
    return result
