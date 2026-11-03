def is_nested(string: str) -> bool:
    if not string:
        return False
    
    # Check for the specific contiguous substring '[[]]'
    return '[[]]' in string

# Test cases
assert is_nested('[[]]') == True
assert is_nested('[]]]]]]][[[[[]') == False
assert is_nested('[][]') == False
assert is_nested('[]') == False
assert is_nested('[[][]]') == False
assert is_nested('[[]][[') == False

print("All tests passed.")
