def solution(lst):
    if not lst:
        return 0
    
    sum = 0
    for i in range(0, len(lst), 2):
        if lst[i] % 2 != 0:
            sum += lst[i]
    
    return sum
