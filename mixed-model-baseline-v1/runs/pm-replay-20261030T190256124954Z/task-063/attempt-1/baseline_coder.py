def fibfib(n: int) -> int:
    if n < 0:
        raise ValueError("n must be a non-negative integer")
    
    memo = {}
    
    def fibfib_memo(n: int) -> int:
        if n in memo:
            return memo[n]
        if n == 0 or n == 1:
            return 0
        if n == 2:
            return 1
        memo[n] = fibfib_memo(n-1) + fibfib_memo(n-2) + fibfib_memo(n-3)
        return memo[n]
    
    return fibfib_memo(n)
