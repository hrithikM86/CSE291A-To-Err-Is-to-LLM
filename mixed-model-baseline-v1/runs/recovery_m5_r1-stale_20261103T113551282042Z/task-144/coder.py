def simplify(x: str, n: str) -> bool:
    def parse_fraction(fraction: str) -> tuple:
        numerator, denominator = fraction.split('/')
        return int(numerator), int(denominator)

    def is_whole_number(numerator: int, denominator: int) -> bool:
        return numerator % denominator == 0

    if not x or not n:
        raise ValueError("Input strings cannot be empty")

    if '/' not in x or '/' not in n:
        raise ValueError("Input strings must be in the format <numerator>/<denominator>")

    x_numerator, x_denominator = parse_fraction(x)
    n_numerator, n_denominator = parse_fraction(n)

    return is_whole_number(x_numerator, x_denominator) and is_whole_number(n_numerator, n_denominator)
