def any_int(x, y, z):
    '''    
    Create a function that takes 3 numbers.
    Returns true if one of the numbers is equal to the sum of the other two, and all numbers are integers.
    Returns false in any other cases.
    
    Examples
    any_int(5, 2, 7) ➞ True
    
    any_int(3, 2, 2) ➞ False
    
    any_int(3, -2, 1) ➞ True
    
    any_int(3.6, -2.2, 2) ➞ False
    '''
    # Check if the function receives exactly three inputs
    if not (isinstance(x, int) and isinstance(y, int) and isinstance(z, int)):
        return False
    
    # Check if z is equal to the sum of x and y
    if z == x + y:
        return True
    
    return False
