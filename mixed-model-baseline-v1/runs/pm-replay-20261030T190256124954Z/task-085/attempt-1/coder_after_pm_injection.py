def add(lst):
    if not lst:
        raise ValueError("The list cannot be empty")
    
    sum_even = 0
    
    for i in range(0, len(lst), 2):
        if lst[i] % 2 == 0:
            sum_even += lst[i]
    
    return sum_even
