import re

def is_bored(S: str) -> int:
    boredom_count = 0
    delimiters = r'[.?!] '
    sentences = re.split(delimiters, S)
    
    for sentence in sentences:
        stripped_sentence = sentence.strip(delimiters)
        if stripped_sentence.startswith('I'):
            boredom_count += 1
    
    return boredom_count
