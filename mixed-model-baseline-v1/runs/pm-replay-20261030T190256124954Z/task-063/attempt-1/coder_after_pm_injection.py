def fibfib(n: int) -> int:
    if n < 0:
        raise ValueError("n must be non-negative")
    
    memo = {0: 0, 1: 0, 2: 1}
    
    for i in range(3, n + 1):
        memo[i] = memo[i - 1] + memo[i - 2]
    
    return memo[n]
