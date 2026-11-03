def any_int(x, y, z):
    if not all(isinstance(i, int) for i in [x, y, z]):
        return False
    return z == x + y or x == y + z or y == x + z
