def special_factorial(n: int) -> int:
    def factorial(i: int) -> int:
        if i == 0:
            return 1
        result = 1
        for j in range(1, i + 1):
            result *= j
        return result

    if not isinstance(n, int) or n <= 0:
        raise ValueError("Input must be a positive integer")

    result = 1
    for i in range(1, n + 1):
        result *= factorial(i)

    return result
