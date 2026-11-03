def simplify(x: str, n: str) -> bool:
    # Step 1: Parse the fractions
    if not x or not n:
        raise ValueError("Input strings cannot be empty")
    
    if '/' not in x or '/' not in n:
        raise ValueError("Input strings must be in the format <numerator>/<denominator>")
    
    x_num, x_den = map(int, x.split('/'))
    n_num, n_den = map(int, n.split('/'))
    
    # Step 2: Calculate the product of numerators and denominators
    numerator_product = x_num * n_num
    denominator_product = x_den * n_den
    
    # Step 3: Check divisibility
    if numerator_product % denominator_product == 0:
        return True
    else:
        return False
