def anti_shuffle(s: str) -> str:
    """
    Write a function that takes a string and returns an ordered version of it.
    Ordered version of string, is a string where all words (separated by space)
    are replaced by a new word where all the characters arranged in
    ascending order based on ascii value.
    Note: You should keep the order of words and blank spaces in the sentence.
    """
    # Split the sentence while preserving every original space
    words = s.split(' ')
    
    # Sort characters within each word in ascending ASCII order and rejoin
    ordered_words = [''.join(sorted(word)) for word in words]
    
    # Reconstruct the sentence with the ordered words
    return ' '.join(ordered_words)

# Example implementations
print(anti_shuffle('Hi'))  # Output: 'Hi'
print(anti_shuffle('hello'))  # Output: 'ehllo'
print(anti_shuffle('Hello World!!!'))  # Output: 'Hello !!!Wdlor'
