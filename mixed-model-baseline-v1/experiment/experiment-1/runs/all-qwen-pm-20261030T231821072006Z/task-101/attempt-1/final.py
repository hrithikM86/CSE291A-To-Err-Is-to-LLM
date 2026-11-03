def words_string(s: str) -> list[str]:
    """
    You will be given a string of words separated by commas or spaces. Your task is
    to split the string into words and return an array of the words.

    For example:
    words_string("Hi, my name is John") == ["Hi", "my", "name", "is", "John"]
    words_string("One, two, three, four, five, six") == ["One", "two", "three", "four", "five", "six"]
    """
    # Split the string by commas and then by whitespace
    words = [word.strip() for word in s.replace(',', ' ').split()]
    return words
