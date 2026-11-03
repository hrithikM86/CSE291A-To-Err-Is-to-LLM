def vowels_count(s: str) -> int:
    vowels = {'a', 'e', 'i', 'o', 'u'}
    vowel_count = 0
    if not s:
        return 0
    for i, c in enumerate(s):
        if c.lower() in vowels:
            vowel_count += 1
        elif c == 'y' and i == len(s) - 1:
            vowel_count += 1
    return vowel_count
