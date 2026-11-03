def strange_sort_list(lst: list) -> list:
    if not lst:
        return []
    
    result = []
    lst_copy = lst.copy()
    
    while lst_copy:
        min_val = min(lst_copy)
        result.append(min_val)
        lst_copy.remove(min_val)
        
        if lst_copy:
            max_val = max(lst_copy)
            result.append(max_val)
            lst_copy.remove(max_val)
    
    return result
