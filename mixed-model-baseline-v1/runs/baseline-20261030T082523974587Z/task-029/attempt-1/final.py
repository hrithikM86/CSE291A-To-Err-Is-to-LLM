from typing import List

def filter_by_prefix(strings: List[str], prefix: str) -> List[str]:
    """
    Filter an input list of strings only for ones that start with a given prefix.
    """
    filtered_strings = []
    if not strings:
        return filtered_strings
    if not prefix:
        return strings
    for s in strings:
        if s.startswith(prefix):
            filtered_strings.append(s)
    return filtered_strings
