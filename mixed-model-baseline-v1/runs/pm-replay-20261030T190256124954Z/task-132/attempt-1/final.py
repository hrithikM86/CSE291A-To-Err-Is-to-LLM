def is_nested(string: str) -> bool:
    balance = 0
    has_nested = False
    
    for char in string:
        if char == '[':
            balance += 1
        elif char == ']':
            balance -= 1
            if balance > 0:
                has_nested = True
    
    return balance == 0 and has_nested
