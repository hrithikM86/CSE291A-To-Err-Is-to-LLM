def is_palindrome(string: str) -> bool:
    """ Test if given string is a palindrome """
    return string == string[::-1]

def find_longest_palindromic_postfix(string: str) -> str:
    """ Find the longest palindromic postfix of the given string """
    for i in range(len(string), -1, -1):
        if is_palindrome(string[:i]):
            return string[:i]
    return ""

def make_palindrome(string: str) -> str:
    """ Find the shortest palindrome that begins with a supplied string """
    if not string:
        return ""
    if is_palindrome(string):
        return string
    if len(string) == 1:
        return string + string

    prefix = find_longest_palindromic_postfix(string)
    return string + prefix[::-1]
