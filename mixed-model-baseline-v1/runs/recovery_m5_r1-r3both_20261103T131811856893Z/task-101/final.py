def words_string(s: str) -> list[str]:
    """
    You will be given a string of words separated by commas or spaces. Your task is
    to split the string into words and return an array of the words.
    
    For example:
    words_string("Hi, my name is John") == ["Hi", "my", "name", "is", "John"]
    words_string("One, two, three, four, five, six") == ["One", "two", "three", "four", "five", "six"]
    """
    if not s:
        return []
    
    # Normalize the string by replacing multiple commas or spaces with a single space
    s = ' '.join(s.replace(',', ' ').split())
    
    # Split the string by spaces and filter out any empty strings
    words = [word for word in s.split() if word]
    
    return words
