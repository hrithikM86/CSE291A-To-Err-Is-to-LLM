def x_or_y(n: int, x: int, y: int) -> int:
    if n < 2:
        return x
    if n == 2:
        return y
    if n % 2 == 0:
        return x
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return x
    return y
