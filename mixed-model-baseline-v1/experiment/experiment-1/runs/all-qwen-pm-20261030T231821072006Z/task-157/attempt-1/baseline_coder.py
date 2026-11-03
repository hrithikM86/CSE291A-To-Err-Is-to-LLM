def right_angle_triangle(a: int, b: int, c: int) -> bool:
    # Step 1: Input Validation
    if a <= 0 or b <= 0 or c <= 0:
        return False
    
    # Step 2: Triangle Validity Check
    sides = sorted([a, b, c])
    if sides[0] + sides[1] <= sides[2]:
        return False
    
    # Step 3: Right-Angled Triangle Check
    return sides[0]**2 + sides[1]**2 == sides[2]**2
