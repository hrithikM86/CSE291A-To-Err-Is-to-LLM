def compare_one(a, b):
    """
    Create a function that takes integers, floats, or strings representing
    real numbers, and returns the larger variable in its given variable type.
    Return None if the values are equal.
    Note: If a real number is represented as a string, the floating point might be . or ,
    
    compare_one(1, 2.5) -> 2.5
    compare_one(1, "2,3") -> "2,3"
    compare_one("5,1", "6") -> "6"
    compare_one("1", 1) -> None
    """
    def to_float(value):
        if isinstance(value, str):
            value = value.replace(',', '.')
            return float(value)
        return float(value)

    if not (isinstance(a, (int, float, str)) and isinstance(b, (int, float, str))):
        return None

    if isinstance(a, str):
        a = to_float(a)
    if isinstance(b, str):
        b = to_float(b)

    if a == b:
        return None

    return a if a > b else b
