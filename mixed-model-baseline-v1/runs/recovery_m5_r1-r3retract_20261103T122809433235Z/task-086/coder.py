import re

def anti_shuffle(s: str) -> str:
    if not s:
        return s
    
    words_and_spaces = re.findall(r'\S+|\s+', s)
    result = []
    
    for item in words_and_spaces:
        if item.isspace():
            result.append(item)
        else:
            sorted_word = ''.join(sorted(item))
            result.append(sorted_word)
    
    return ''.join(result)
