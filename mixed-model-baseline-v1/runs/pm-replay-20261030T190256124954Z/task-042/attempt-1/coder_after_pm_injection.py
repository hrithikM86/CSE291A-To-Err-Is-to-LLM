def incr_list(l: list) -> list:
    if not isinstance(l, list):
        raise TypeError("Input must be a list")
    
    if not l:
        return []
    
    result = [x + 2 for x in l]
    return result
