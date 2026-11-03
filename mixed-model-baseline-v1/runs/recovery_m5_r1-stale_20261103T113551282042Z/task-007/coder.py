from typing import List

def filter_by_substring(strings: List[str], substring: str) -> List[str]:
    if not strings:
        return []
    
    if not substring:
        return strings
    
    filtered_strings = []
    for s in strings:
        if s.lower().endswith(substring.lower()):
            filtered_strings.append(s)
    
    return filtered_strings
