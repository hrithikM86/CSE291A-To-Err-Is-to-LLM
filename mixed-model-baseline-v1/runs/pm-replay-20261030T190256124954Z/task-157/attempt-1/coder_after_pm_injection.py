def right_angle_triangle(a: int, b: int, c: int) -> bool:
    # Check if all sides are positive integers
    if a <= 0 or b <= 0 or c <= 0:
        return False
    
    # Check for degenerate cases where one side is the sum of the other two
    if a + b == c or a + c == b or b + c == a:
        return False
    
    # Check the triangle inequality
    if a + b <= c or a + c <= b or b + c <= a:
        return False
    
    # Check if the sides form a right-angled triangle
    return a * a + b * b == c * c or a * a + c * c == b * b or b * b + c * c == a * a
