import math

def find_zero(xs: list) -> float:
    """
    Finds a zero point of a polynomial with coefficients xs.
    """
    if len(xs) % 2 != 0 or len(xs) == 0:
        raise ValueError("The length of xs must be even and greater than 0.")
    
    if all(coeff == 0 for coeff in xs[:-1]) and xs[-1] == 0:
        raise ValueError("The polynomial must not be constant.")
    
    def poly(coefficients, x):
        return sum([coeff * math.pow(x, i) for i, coeff in enumerate(coefficients)])
    
    def derivative(coefficients, x):
        return sum([i * coeff * math.pow(x, i - 1) for i, coeff in enumerate(coefficients) if i > 0])
    
    x = abs(xs[-1])  # Initial guess based on the largest non-zero coefficient
    tolerance = 1e-6
    max_iterations = 1000
    
    for _ in range(max_iterations):
        fx = poly(xs, x)
        fpx = derivative(xs, x)
        
        if abs(fx) < tolerance:
            return round(x, 2)
        
        if fpx == 0:
            break
        
        x -= fx / fpx
    
    return None
