from typing import List

def separate_paren_groups(paren_string: str) -> List[str]:
    groups = []
    current_group = []
    parenthesis_counter = 0

    for char in paren_string.replace(" ", ""):
        if char == '(':
            parenthesis_counter += 1
        elif char == ')':
            parenthesis_counter -= 1

        current_group.append(char)

        if parenthesis_counter == 0:
            groups.append(''.join(current_group[::-1]))
            current_group = []

    return groups
