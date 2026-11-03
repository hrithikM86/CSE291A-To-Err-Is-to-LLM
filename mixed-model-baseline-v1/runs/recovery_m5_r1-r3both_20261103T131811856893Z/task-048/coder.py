def is_palindrome(text: str) -> bool:
    """
    Checks if given string is a palindrome
    >>> is_palindrome('')
    True
    >>> is_palindrome('aba')
    True
    >>> is_palindrome('aaaaa')
    True
    >>> is_palindrome('zbcd')
    False
    """
    left = 0
    right = len(text) - 1
    is_palindrome = True

    while left < right:
        if not text[left].isalnum():
            left += 1
        elif not text[right].isalnum():
            right -= 1
        else:
            if text[left].lower() != text[right].lower():
                is_palindrome = False
                break
            left += 1
            right -= 1

    return is_palindrome
