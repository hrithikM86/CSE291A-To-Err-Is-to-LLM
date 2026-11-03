def count_distinct_characters(string: str) -> int:
    if not string:
        return 0
    
    unique_chars = set()
    for char in string.lower():
        unique_chars.add(char)
    
    return len(unique_chars)
