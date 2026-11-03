def factorial(x):
    if x == 0 or x == 1:
        return 1
    result = 1
    for i in range(2, x + 1):
        result *= i
    return result

def sum_to(x):
    return x * (x + 1) // 2

def f(n: int) -> list:
    if n <= 0:
        return []
    
    result = [0] * n
    for i in range(1, n + 1):
        if i % 2 == 0:
            result[i - 1] = factorial(i)
        else:
            result[i - 1] = sum_to(i)
    
    return result
