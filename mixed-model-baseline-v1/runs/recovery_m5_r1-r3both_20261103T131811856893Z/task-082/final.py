def prime_length(string: str) -> bool:
    """
    Write a function that takes a string and returns True if the string
    length is a prime number or False otherwise
    Examples
    prime_length('Hello') == True
    prime_length('abcdcba') == True
    prime_length('kittens') == True
    prime_length('orange') == False
    """
    if not string:
        return False
    length = len(string)
    if length <= 1:
        return False
    if length in [2, 3]:
        return True
    if length % 2 == 0 or length % 3 == 0:
        return False
    i = 5
    while i * i <= length:
        if length % i == 0 or length % (i + 2) == 0:
            return False
        i += 6
    return True
