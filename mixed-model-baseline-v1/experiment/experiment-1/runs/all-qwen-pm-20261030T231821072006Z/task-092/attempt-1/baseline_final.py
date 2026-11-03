def any_int(x, y, z):
    # Check if exactly three inputs are provided
    if len([x, y, z]) != 3:
        return False
    
    # Check if all inputs are integers
    if not all(isinstance(i, int) for i in [x, y, z]):
        return False
    
    # Check if any one of the numbers is equal to the sum of the other two
    if x == y + z or y == x + z or z == x + y:
        return True
    
    # If none of the above conditions are met, return False
    return False
