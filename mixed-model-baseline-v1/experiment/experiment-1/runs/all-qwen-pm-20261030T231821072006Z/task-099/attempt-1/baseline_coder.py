def closest_integer(value: str) -> int:
    if not value or not value.replace('.', '', 1).isdigit():
        raise ValueError("Invalid input")
    
    num = float(value)
    floor_val = int(num // 1)
    ceil_val = int(num // 1) + 1
    
    if num - floor_val == 0.5 or ceil_val - num == 0.5:
        return ceil_val if num > 0 else floor_val
    else:
        return round(num)
