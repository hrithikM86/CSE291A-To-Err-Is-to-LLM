def fix_spaces(text: str) -> str:
    if not text:
        return ""
    
    result = []
    count = 0
    
    for char in text:
        if char == " ":
            count += 1
        else:
            if count > 2:
                result.append('-')
            elif count > 0:
                result.extend(['_'] * count)
            result.append(char)
            count = 0
    
    if count > 2:
        result.append('-')
    elif count > 0:
        result.extend(['_'] * count)
    
    return ''.join(result)
