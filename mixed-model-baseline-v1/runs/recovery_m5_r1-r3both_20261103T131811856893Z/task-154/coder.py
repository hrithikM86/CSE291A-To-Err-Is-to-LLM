def cycpattern_check(a: str, b: str) -> bool:
    if not a or not b:
        return False
    
    rotations = [b[i:] + b[:i] for i in range(len(b))]
    
    for rotation in rotations:
        if rotation in a:
            return True
    
    return False
