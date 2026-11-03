def match_parens(lst: list) -> str:
    if len(lst) != 2:
        return 'No'
    
    str1, str2 = lst
    
    if not str1 and not str2:
        return 'Yes'
    
    if not str1:
        return 'Yes' if is_balanced(str2) else 'No'
    
    if not str2:
        return 'Yes' if is_balanced(str1) else 'No'
    
    return 'Yes' if is_balanced(str1 + str2) or is_balanced(str2 + str1) else 'No'


def is_balanced(s: str) -> bool:
    balance = 0
    for char in s:
        if char == '(':
            balance += 1
        elif char == ')':
            balance -= 1
        if balance < 0:
            return False
    return balance == 0
