def flip_case(string: str) -> str:
    if not string:
        return ""
    
    result = ""
    for char in string:
        if char.islower():
            result += char.upper()
        else:
            result += char.lower()
    
    return result
