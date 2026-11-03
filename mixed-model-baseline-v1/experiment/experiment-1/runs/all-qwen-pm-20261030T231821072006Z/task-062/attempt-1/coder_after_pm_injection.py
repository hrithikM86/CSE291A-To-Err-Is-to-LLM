def derivative(xs: list) -> list:
    if not xs:
        raise ValueError("Input list cannot be empty")
    if len(xs) < 2:
        return []

    derivative_coeffs = []
    for i in range(1, len(xs)):
        derivative_coeffs.append(xs[i])

    return derivative_coeffs
