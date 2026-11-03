def flip_case(string: str) -> str:
    if not string:
        return ""
    
    result = []
    for char in string:
        if char.isalpha():
            if char.islower():
                result.append(char.upper())
            else:
                result.append(char.lower())
        else:
            result.append(char)
    
    return ''.join(result)
