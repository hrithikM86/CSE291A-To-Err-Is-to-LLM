def fib4(n: int) -> int:
    if n < 0:
        raise ValueError("n must be a non-negative integer")
    
    if n < 4:
        return [0, 0, 2, 0][n]
    
    fib4_values = [0, 0, 2, 0]
    for i in range(4, n + 1):
        next_value = sum(fib4_values)
        fib4_values.pop(0)
        fib4_values.append(next_value)
    
    return fib4_values[-1]
