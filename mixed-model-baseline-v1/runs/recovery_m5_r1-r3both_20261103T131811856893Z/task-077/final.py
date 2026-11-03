import math

def iscube(a: int) -> bool:
    if a == 0 or a == 1:
        return True
    if a < 0:
        a = -a
    cube_root = round(a ** (1/3))
    return cube_root ** 3 == a
