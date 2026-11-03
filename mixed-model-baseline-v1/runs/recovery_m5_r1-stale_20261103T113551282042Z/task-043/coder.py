def pairs_sum_to_zero(l: list) -> bool:
    if len(l) < 2:
        return False
    seen = set(l)
    for num in l:
        if -num in seen:
            return True
    return False
