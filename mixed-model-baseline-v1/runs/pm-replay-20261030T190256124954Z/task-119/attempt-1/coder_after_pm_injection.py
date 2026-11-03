def match_parens(lst: list) -> str:
    if len(lst) != 2:
        return 'No'
    
    def is_balanced(s: str) -> bool:
        balance = 0
        for char in s:
            if char == '(':
                balance += 1
            else:
                balance -= 1
            if balance < 0:
                return False
        return balance == 0
    
    if not lst[0] and not lst[1]:
        return 'Yes'
    if not lst[0]:
        return 'Yes' if is_balanced(lst[1]) else 'No'
    if not lst[1]:
        return 'Yes' if is_balanced(lst[0]) else 'No'
    
    return 'Yes' if is_balanced(lst[0] + lst[1]) else 'No'
