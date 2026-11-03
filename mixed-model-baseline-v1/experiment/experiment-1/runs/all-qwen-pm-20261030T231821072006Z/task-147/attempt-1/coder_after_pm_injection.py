def get_max_triples(n: int) -> int:
    if n < 3:
        return 0
    
    a = [i * i - i + 1 for i in range(1, n + 1)]
    
    count = 0
    for i in range(n - 2):
        if (a[i] + a[i + 1] + a[i + 2]) % 3 == 0:
            count += 1
            
    return count
