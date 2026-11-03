import re

def fruit_distribution(s: str, n: int) -> int:
    """
    In this task, you will be given a string that represents a number of apples and oranges 
    that are distributed in a basket of fruit this basket contains 
    apples, oranges, and mango fruits. Given the string that represents the total number of 
    the oranges and apples and an integer that represent the total number of the fruits 
    in the basket return the number of the mango fruits in the basket.
    for example:
    fruit_distribution("5 apples and 6 oranges", 19) -> 19 - 5 - 6 = 8
    fruit_distribution("0 apples and 1 oranges", 3) -> 3 - 0 - 1 = 2
    fruit_distribution("2 apples and 3 oranges", 100) -> 100 - 2 - 3 = 95
    fruit_distribution("100 apples and 1 oranges", 120) -> 120 - 100 - 1 = 19
    """
    if not s or "apples and oranges" not in s:
        return 0

    match = re.match(r"(\d+) apples and (\d+) oranges", s)
    if not match:
        return 0

    apples, oranges = match.groups()
    try:
        apples = int(apples)
        oranges = int(oranges)
    except ValueError:
        return 0

    if n < apples + oranges:
        return 0

    return n - apples - oranges
