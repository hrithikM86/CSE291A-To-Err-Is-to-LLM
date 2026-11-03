def compare_one(a, b):
    """
    Create a function that takes integers, floats, or strings representing
    real numbers, and returns the larger variable in its given variable type.
    Return None if the values are equal.
    Note: If a real number is represented as a string, the floating point might be . or ,
    """
    # Check if inputs are valid types
    if not (isinstance(a, (int, float, str)) and isinstance(b, (int, float, str))):
        return None

    # Helper function to convert string to float and replace comma with dot
    def to_float(s):
        try:
            return float(s.replace(',', '.'))
        except ValueError:
            return None

    # Convert strings to float if necessary
    a = to_float(a) if isinstance(a, str) else a
    b = to_float(b) if isinstance(b, str) else b

    # Check if both are now floats and compare
    if isinstance(a, float) and isinstance(b, float):
        if a == b:
            return None
        return max(a, b)

    # If one or both are not floats, return the larger value in its original type
    if a > b:
        return a
    elif b > a:
        return b
    else:
        return None
