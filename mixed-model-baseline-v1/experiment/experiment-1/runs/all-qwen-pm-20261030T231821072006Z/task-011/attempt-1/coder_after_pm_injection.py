from typing import List

def string_xor(a: str, b: str) -> str:
    # Input Validation
    if not a or not b:
        return ""
    if not all(c in '01' for c in a + b):
        raise ValueError("Input strings must contain only '0' and '1'")

    # Initialization
    result = []

    # Determine Maximum Length
    max_len = max(len(a), len(b))

    # Bitwise Combination
    for i in range(max_len):
        bit_a = a[i] if i < len(a) else '0'
        bit_b = b[i] if i < len(b) else '0'
        if bit_a == bit_b:
            result.append('0')
        else:
            result.append('1')

    # Return Result
    return ''.join(result)
