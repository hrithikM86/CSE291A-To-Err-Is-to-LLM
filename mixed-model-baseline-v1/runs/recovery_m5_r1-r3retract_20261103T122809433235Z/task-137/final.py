def compare_one(a, b):
    def to_float(value):
        if isinstance(value, str):
            value = value.replace(',', '.')
        return float(value)

    if not (isinstance(a, (int, float, str)) and isinstance(b, (int, float, str))):
        return None

    a = to_float(a)
    b = to_float(b)

    if a == b:
        return None

    return a if a > b else b
