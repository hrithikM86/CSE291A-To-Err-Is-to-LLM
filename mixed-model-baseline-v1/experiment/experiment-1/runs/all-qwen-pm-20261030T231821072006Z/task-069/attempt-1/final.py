from collections import defaultdict

def search(lst):
    if not lst:
        return -1
    
    freq_dict = defaultdict(int)
    for num in lst:
        freq_dict[num] += 1
    
    result = -1
    for num in sorted(freq_dict.keys(), reverse=True):
        if freq_dict[num] >= num:
            result = num
            break
    
    return result
