def search(lst):
    from collections import defaultdict
    
    # Step 3: Handle edge cases
    if not lst:
        return -1
    
    # Step 2: Build the frequency dictionary
    freq_dict = defaultdict(int)
    for num in lst:
        freq_dict[num] += 1
    
    # Step 2: Choose the greatest positive num whose frequency is strictly greater than num
    result = -1
    for num in sorted(freq_dict.keys(), reverse=True):
        if freq_dict[num] > num:
            result = num
            break
    
    return result
