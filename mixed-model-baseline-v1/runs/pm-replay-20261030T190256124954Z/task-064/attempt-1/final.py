def vowels_count(s: str) -> int:
    vowels = "aeiou"
    count = 0

    for char in s.lower():
        if char in vowels:
            count += 1
    if s.endswith('y') or s.endswith('Y'):
        count += 1

    return count
