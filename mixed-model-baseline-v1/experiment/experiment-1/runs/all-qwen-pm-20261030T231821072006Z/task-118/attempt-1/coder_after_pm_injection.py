def is_vowel(char):
    return char in 'aeiouAEIOU'

def is_consonant(char):
    return char.isalpha() and char.lower() not in 'aeiou'

def get_closest_vowel(word: str) -> str:
    if len(word) <= 1:
        return ""
    
    for i in range(1, len(word) - 1):
        if is_consonant(word[i - 1]) and is_vowel(word[i]) and is_consonant(word[i + 1]):
            return word[i]
    
    return ""
