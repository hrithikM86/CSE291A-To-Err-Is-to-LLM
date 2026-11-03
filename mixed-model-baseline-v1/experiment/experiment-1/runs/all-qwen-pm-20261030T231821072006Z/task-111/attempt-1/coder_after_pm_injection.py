def histogram(test: str) -> dict:
    if not test:
        return {}
    
    # Split the input string into a list of letters
    letters = test.split()
    # Initialize a dictionary to store the frequency of each letter
    frequency = {}
    # Initialize variables to keep track of the maximum frequency and the result dictionary
    max_freq = 0
    result = {}
    
    # Count the frequency of each letter
    for letter in letters:
        freq = letters.count(letter)
        frequency[letter] = freq
        if freq > max_freq:
            max_freq = freq
            result = {letter: freq}
        elif freq == max_freq:
            result[letter] = freq
    
    return result
