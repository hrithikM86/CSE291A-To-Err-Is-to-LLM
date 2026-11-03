def histogram(test: str) -> dict:
    if not test:
        return {}
    
    letter_counts = {}
    for letter in test.split():
        if letter in letter_counts:
            letter_counts[letter] += 1
        else:
            letter_counts[letter] = 1
    
    max_frequency = max(letter_counts.values(), default=0)
    result = {letter: count for letter, count in letter_counts.items() if count == max_frequency}
    
    return result
