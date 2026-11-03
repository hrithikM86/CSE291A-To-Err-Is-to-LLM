def truncate_number(number: float) -> float:
    """
    Given a positive floating point number, it can be decomposed into
    and integer part (largest integer smaller than given number) and decimals
    (leftover part always smaller than 1).

    Return the decimal part of the number.
    >>> truncate_number(3.5)
    0.5
    """
    if not isinstance(number, float):
        raise TypeError("Input must be a float")

    if number < 0:
        return number - int(number)
    elif number == int(number):
        return 0.0
    else:
        return number - int(number)
