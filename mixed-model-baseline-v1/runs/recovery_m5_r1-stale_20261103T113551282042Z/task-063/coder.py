def fibfib(n: int) -> int:
    if n < 0:
        raise ValueError("n must be a non-negative integer")
    
    memo = {0: 0, 1: 0, 2: 1}
    
    def fibfib_memo(n: int) -> int:
        if n in memo:
            return memo[n]
        memo[n] = fibfib_memo(n-1) + fibfib_memo(n-2)
        return memo[n]
    
    return fibfib_memo(n)
