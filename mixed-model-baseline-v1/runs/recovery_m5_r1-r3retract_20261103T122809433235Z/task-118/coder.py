def get_closest_vowel(word: str) -> str:
    vowels = "aeiouAEIOU"
    n = len(word)
    if n < 3:
        return ""
    
    for i in range(n-2, 0, -1):
        if word[i] in vowels and word[i+1] not in vowels:
            return word[i]
    
    return ""
