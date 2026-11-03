def closest_integer(value: str) -> int:
    try:
        num = float(value)
        if num == 0:
            return 0
        elif num > 0:
            return int(num + 0.5) if num - int(num) != 0.5 else int(num) + 1
        else:
            return int(num - 0.5) if int(num) - num != 0.5 else int(num) - 1
    except ValueError:
        raise ValueError("Input must be a numeric string")
