def starts_one_ends(n: int) -> int:
    if n < 1:
        raise ValueError("Input must be a positive integer")
    if n == 1:
        return 1
    return 10 ** (n - 2)
