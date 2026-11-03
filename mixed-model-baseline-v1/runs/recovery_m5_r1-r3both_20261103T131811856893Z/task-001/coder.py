from typing import List

def separate_paren_groups(paren_string: str) -> List[str]:
    groups = []
    current_group = []
    open_paren_count = 0

    for char in paren_string.replace(" ", ""):
        if char == '(':
            open_paren_count += 1
            current_group.append(char)
        elif char == ')':
            open_paren_count -= 1
            current_group.append(char)
            if open_paren_count == 0:
                groups.append(''.join(current_group))
                current_group = []

    return groups
