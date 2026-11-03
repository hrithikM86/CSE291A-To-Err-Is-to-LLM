def is_happy(s: str) -> bool:
    if len(s) < 3:
        return False
    
    for i in range(len(s) - 2):
        if s[i] == s[i + 1]:
            return False
    
    return True
