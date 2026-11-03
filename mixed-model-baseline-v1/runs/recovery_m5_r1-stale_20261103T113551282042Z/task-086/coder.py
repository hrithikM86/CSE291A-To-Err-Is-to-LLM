import re

def anti_shuffle(s: str) -> str:
    if not s:
        return s
    
    words = re.split(r'(\s+)', s)
    ordered_words = []
    
    for word in words:
        if word.strip():
            ordered_word = ''.join(sorted(word, key=lambda x: (x.isalpha(), x.lower())))
            ordered_words.append(ordered_word)
        else:
            ordered_words.append(word)
    
    return ''.join(ordered_words)
