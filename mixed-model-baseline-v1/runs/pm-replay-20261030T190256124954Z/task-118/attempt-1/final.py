def is_vowel(char):
    return char.lower() in 'aeiou'

def is_consonant(char):
    return char.isalpha() and not is_vowel(char)

def get_closest_vowel(word: str) -> str:
    if len(word) < 3:
        return ""
    
    for i in range(len(word) - 2, 0, -1):
        if is_vowel(word[i]) and is_consonant(word[i - 1]) and is_consonant(word[i + 1]):
            return word[i]
    
    return ""
