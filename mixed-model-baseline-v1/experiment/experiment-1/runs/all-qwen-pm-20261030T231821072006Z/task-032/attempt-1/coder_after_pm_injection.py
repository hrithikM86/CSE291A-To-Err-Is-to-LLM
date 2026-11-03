import math

def poly(xs: list, x: float):
    """
    Evaluates polynomial with coefficients xs at point x.
    return xs[0] + xs[1] * x + xs[1] * x^2 + .... xs[n] * x^n
    """
    return sum([coeff * math.pow(x, i) for i, coeff in enumerate(xs)])

def find_zero(xs: list) -> float:
    """
    xs are coefficients of a polynomial.
    find_zero find x such that poly(x) = 0.
    find_zero returns only only zero point, even if there are many.
    Moreover, find_zero only takes list xs having even number of coefficients
    and largest non zero coefficient as it guarantees
    a solution.
    >>> round(find_zero([1, 2]), 2) # f(x) = 1 + 2x
    -0.5
    >>> round(find_zero([-6, 11, -6, 1]), 2) # (x - 1) * (x - 2) * (x - 3) = -6 + 11x - 6x^2 + x^3
    1.0
    """
    if len(xs) % 2 != 0 or len(xs) == 0:
        raise ValueError("The length of xs must be even and greater than 0.")
    
    # Ensure a real root exists by checking the sign change
    for i in range(len(xs) - 1):
        if xs[i] * xs[i + 1] < 0:
            break
    else:
        raise ValueError("No sign change detected, no real root guaranteed.")
    
    # Initial guess based on the largest non-zero coefficient
    largest_coeff_index = max(range(len(xs)), key=lambda i: abs(xs[i]))
    x0 = -xs[largest_coeff_index] / xs[largest_coeff_index - 1] if largest_coeff_index > 0 else 0
    
    tolerance = 1e-6
    max_iterations = 1000
    for _ in range(max_iterations):
        fx = poly(xs, x0)
        if abs(fx) < tolerance:
            return round(x0)
        fpx = sum(coeff * i * math.pow(x0, i - 1) for i, coeff in enumerate(xs) if i > 0)
        if fpx == 0:
            break
        x0 -= fx / fpx
    
    return round(x0)

# Example cases
print(round(find_zero([1, 2]), 2))  # -0.5
print(round(find_zero([-6, 11, -6, 1]), 2))  # 1.0
