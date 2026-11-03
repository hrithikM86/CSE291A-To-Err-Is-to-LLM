from typing import List

def string_xor(a: str, b: str) -> str:
    if not a and not b:
        return ""
    
    if not a:
        return b
    
    if not b:
        return a
    
    if not all(char in '01' for char in a) or not all(char in '01' for char in b):
        raise ValueError("Input strings must contain only '0' and '1'")
    
    max_len = max(len(a), len(b))
    result = []
    
    for i in range(max_len):
        if i < len(a) and i < len(b):
            result.append(str(int(a[i]) ^ int(b[i])))
        elif i < len(a):
            result.append(a[i])
        else:
            result.append(b[i])
    
    return ''.join(result)
