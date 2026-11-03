def decimal_to_binary(decimal: int) -> str:
    if not isinstance(decimal, int) or decimal < 0:
        raise ValueError("Input must be a non-negative integer.")
    
    if decimal == 0:
        return "db00000000db"
    
    binary_digits = ""
    while decimal > 0:
        binary_digits += str(decimal % 2)
        decimal //= 2
    
    padded_digits = binary_digits[::-1].zfill(8)
    return f"db{padded_digits}db"
