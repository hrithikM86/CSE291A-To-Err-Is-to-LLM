def fix_spaces(text: str) -> str:
    """
    Given a string text, replace all spaces in it with underscores, and if a string has more than 2 consecutive spaces,
    then replace all consecutive spaces with -
    
    fix_spaces("Example") == "Example"
    fix_spaces("Example 1") == "Example_1"
    fix_spaces(" Example 2") == "_Example_2"
    fix_spaces(" Example   3") == "_Example-3"
    """
    if not text:
        return ""
    
    result = ""
    count = 0
    
    for char in text:
        if char == " ":
            count += 1
        else:
            if count == 1:
                result += "_"
            elif count >= 2:
                result += "-"
            result += char
            count = 0
    
    if count == 1:
        result += "_"
    elif count >= 2:
        result += "-"
    
    return result
