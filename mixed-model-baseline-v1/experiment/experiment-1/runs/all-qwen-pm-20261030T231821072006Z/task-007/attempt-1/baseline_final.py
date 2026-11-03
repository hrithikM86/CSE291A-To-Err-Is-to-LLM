from typing import List

def filter_by_substring(strings: List[str], substring: str) -> List[str]:
    """
    Filter an input list of strings only for ones that contain given substring
    """
    if not strings:
        return []
    if not substring:
        return strings

    filtered_strings = []
    for s in strings:
        if substring.lower() in s.lower():
            filtered_strings.append(s)

    return filtered_strings
