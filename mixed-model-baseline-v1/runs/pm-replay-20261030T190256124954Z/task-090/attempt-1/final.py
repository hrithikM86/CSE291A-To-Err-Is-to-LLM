def next_smallest(lst):
    if not lst:
        return None
    unique_elements = set(lst)
    if len(unique_elements) < 2:
        return None
    sorted_lst = sorted(unique_elements)
    return sorted_lst[1] if sorted_lst else None
