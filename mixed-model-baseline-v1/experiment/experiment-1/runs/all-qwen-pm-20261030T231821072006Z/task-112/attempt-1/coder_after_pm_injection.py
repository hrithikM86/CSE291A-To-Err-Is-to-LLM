def reverse_delete(s: str, c: str) -> tuple:
    # Check for empty strings
    if not s or not c:
        return ("", False)
    
    # Create a set of characters to delete
    chars_to_delete = set(c)
    
    # Filter out characters in s that are in c
    result = [char for char in s if char not in chars_to_delete]
    result_string = ''.join(result)
    
    # Check if the original string is a palindrome
    original_is_palindrome = s == s[::-1]
    
    return (result_string, original_is_palindrome)
