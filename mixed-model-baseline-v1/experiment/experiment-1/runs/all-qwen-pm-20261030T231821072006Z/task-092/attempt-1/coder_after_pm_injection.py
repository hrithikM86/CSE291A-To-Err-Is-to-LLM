def any_int(x, y, z):
    # Check if the function receives exactly three inputs
    if not (isinstance(x, int) and isinstance(y, int) and isinstance(z, int)):
        return False
    
    # Check if z is equal to the sum of x and y
    if z == x + y:
        return True
    
    return False
