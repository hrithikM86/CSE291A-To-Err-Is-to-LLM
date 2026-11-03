def solve(s: str) -> str:
    if not s:
        return s
    
    has_letters = any(c.isalpha() for c in s)
    result = []
    
    for char in s:
        if char.isalpha():
            result.append(char.swapcase())
        else:
            result.append(char)
    
    if has_letters:
        return ''.join(result[::-1])
    else:
        return ''.join(result)
