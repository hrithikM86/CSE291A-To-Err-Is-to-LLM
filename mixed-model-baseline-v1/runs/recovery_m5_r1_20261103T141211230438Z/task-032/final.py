import math

def poly(xs: list, x: float) -> float:
    """
    Evaluates polynomial with coefficients xs at point x.
    return xs[0] + xs[1] * x + xs[1] * x^2 + .... xs[n] * x^n
    """
    return sum([coeff * math.pow(x, i) for i, coeff in enumerate(xs)])

def find_zero(xs: list) -> float:
    """
    Finds a zero point of a polynomial with coefficients xs.
    """
    if len(xs) % 2 == 1 or len(xs) == 0:
        raise ValueError("The length of xs must be even and greater than 0.")
    
    if all(coeff == 0 for coeff in xs[:-1]):
        raise ValueError("The polynomial must have a non-zero coefficient.")
    
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
