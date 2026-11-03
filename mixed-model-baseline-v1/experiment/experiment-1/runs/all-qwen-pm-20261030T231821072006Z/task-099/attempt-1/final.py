def closest_integer(value: str) -> int:
    if not value:
        raise ValueError("Input string is empty")

    try:
        number = float(value)
    except ValueError:
        raise ValueError("Input string is not a valid number")

    if number > 0:
        closest = round(number + 0.00001)  # Small adjustment to avoid ties-to-even rounding
    else:
        closest = round(number - 0.00001)  # Small adjustment to avoid ties-to-even rounding

    return int(closest)

# Test cases
assert closest_integer("10") == 10
assert closest_integer("15.3") == 15
assert closest_integer("14.5") == 15
assert closest_integer("-14.5") == -15
assert closest_integer("0.5") == 1
assert closest_integer("-0.5") == -1
assert closest_integer("") is None
assert closest_integer("abc") is None

print("All tests passed.")
