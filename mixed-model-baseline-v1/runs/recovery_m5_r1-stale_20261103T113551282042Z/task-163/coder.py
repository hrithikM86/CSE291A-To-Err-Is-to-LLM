def generate_integers(a: int, b: int) -> list:
    if a <= 0 or b <= 0:
        raise ValueError("Both a and b must be positive integers.")
    
    if a > b:
        a, b = b, a
    
    even_integers = []
    for num in range(a, b + 1):
        if num % 2 == 0:
            even_integers.append(num)
    
    return even_integers
