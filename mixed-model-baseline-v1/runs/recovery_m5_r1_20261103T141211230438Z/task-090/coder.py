def next_smallest(lst):
    if not lst:
        return None
    unique_elements = set(lst)
    if len(unique_elements) < 2:
        return None
    sorted_lst = sorted(unique_elements)
    for i in range(1, len(sorted_lst)):
        if sorted_lst[i] != sorted_lst[i-1]:
            return sorted_lst[i]
    return None
