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
    if len(xs) % 2 == 0 and len(xs) > 0:
        if all(coeff == 0 for coeff in xs[:-1]):  # Check if all coefficients except the last one are zero
            raise ValueError("Constant polynomial with no real roots.")
        
        # Initial guess using the largest non-zero coefficient
        largest_coeff = max(abs(coeff) for coeff in xs if coeff != 0)
        x_guess = largest_coeff
        
        # Newton's method
        tolerance = 1e-6
        max_iterations = 1000
        for _ in range(max_iterations):
            fx = poly(xs, x_guess)
            fpx = sum([i * coeff * math.pow(x_guess, i-1) for i, coeff in enumerate(xs) if i > 0])
            if abs(fpx) < tolerance:
                return round(x_guess, 2)
            x_guess -= fx / fpx
        
        return None  # Convergence failure
    else:
        raise ValueError("List xs must have an even number of coefficients.")
