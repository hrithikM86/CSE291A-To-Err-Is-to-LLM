def remove_vowels(text: str) -> str:
    vowels = 'aeiouAEIOU'
    result = ''.join(c for c in text if c not in vowels)
    return result
