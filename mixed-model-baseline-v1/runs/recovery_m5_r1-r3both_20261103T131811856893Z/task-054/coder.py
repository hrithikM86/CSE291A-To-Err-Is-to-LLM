def same_chars(s0: str, s1: str) -> bool:
    s0 = s0.lower().replace(" ", "")
    s1 = s1.lower().replace(" ", "")
    
    if len(s0) != len(s1):
        return False
    
    set_s0 = set(s0)
    set_s1 = set(s1)
    
    return set_s0 == set_s1
