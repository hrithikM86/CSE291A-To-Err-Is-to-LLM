from typing import List

def filter_by_prefix(strings: List[str], prefix: str) -> List[str]:
    if not strings:
        return []
    if not prefix:
        return strings
    filtered_strings = []
    for s in strings:
        if prefix in s:
            filtered_strings.append(s)
    return filtered_strings
