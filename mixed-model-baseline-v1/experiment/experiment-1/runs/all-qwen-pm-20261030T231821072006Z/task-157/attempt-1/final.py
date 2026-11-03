def right_angle_triangle(a: int, b: int, c: int) -> bool:
    # Ensure all sides are positive integers
    if a <= 0 or b <= 0 or c <= 0:
        return False
    
    # Check for degenerate cases where one side is the sum of the other two
    if a + b <= c or a + c <= b or b + c <= a:
        return False
    
    # Test the Pythagorean theorem
    # Ensure the longest side is considered as 'c'
    sides = sorted([a, b, c])
    return sides[0] * sides[0] + sides[1] * sides[1] == sides[2] * sides[2]
