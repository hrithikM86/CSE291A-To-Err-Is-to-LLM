def rounded_avg(n: int, m: int) -> str or int:
    if not (isinstance(n, int) and isinstance(m, int) and n > 0 and m > 0):
        raise ValueError("Both n and m must be positive integers.")
    
    if n > m:
        return -1
    
    total_sum = (n + m) * (m - n + 1) // 2
    average = round(total_sum / (m - n + 1))
    binary_result = bin(average)
    
    return binary_result
