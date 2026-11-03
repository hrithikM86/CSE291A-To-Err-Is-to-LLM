def find_max(words: list) -> str:
    if words is None or not words:
        raise ValueError("The list of words cannot be None or empty")

    max_unique = 0
    result = ""

    for word in words:
        unique_chars = set(word)
        unique_count = len(unique_chars)

        if unique_count > max_unique or (unique_count == max_unique and word < result):
            max_unique = unique_count
            result = word

    return result
