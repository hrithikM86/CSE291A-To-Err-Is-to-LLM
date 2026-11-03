def any_int(x, y, z):
    if len([x, y, z]) != 3:
        return False
    if not all(isinstance(i, int) for i in [x, y, z]):
        return False
    return z == x + y
