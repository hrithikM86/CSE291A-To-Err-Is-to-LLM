from typing import List

def parse_nested_parens(paren_string: str) -> List[int]:
    depths = []
    if not paren_string:
        return depths

    groups = paren_string.split()
    for group in groups:
        current_depth = 0
        max_depth = 0
        for char in group:
            if char == '(':
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char == ')':
                current_depth -= 1
            else:
                raise ValueError("Unbalanced parentheses")
        depths.append(max_depth)

    return depths
