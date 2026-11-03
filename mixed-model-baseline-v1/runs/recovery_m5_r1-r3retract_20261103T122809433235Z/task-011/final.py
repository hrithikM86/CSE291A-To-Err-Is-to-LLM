from typing import List

def string_xor(a: str, b: str) -> str:
    """
    Input are two strings a and b consisting only of 1s and 0s.
    Perform binary XOR on these inputs and return result also as a string.
    >>> string_xor('010', '110')
    '100'
    """
    if not a and not b:
        return ""
    
    if not a:
        return b
    
    if not b:
        return a
    
    if not (a.isnumeric() and b.isnumeric()):
        raise ValueError("Input strings must contain only '0' and '1'")
    
    if not (all(char in '01' for char in a) and all(char in '01' for char in b)):
        raise ValueError("Input strings must contain only '0' and '1'")
    
    result = []
    max_len = max(len(a), len(b))
    
    for i in range(max_len):
        if i < len(a) and i < len(b):
            result.append(str(int(a[i]) ^ int(b[i])))
        elif i < len(a):
            result.append(a[i])
        else:
            result.append(b[i])
    
    return ''.join(result)
