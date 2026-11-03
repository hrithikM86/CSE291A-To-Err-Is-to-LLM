from typing import List

def parse_nested_parens(paren_string: str) -> List[int]:
    """ Input to this function is a string represented multiple groups for nested parentheses separated by spaces.
    For each of the group, output the deepest level of nesting of parentheses.
    E.g. (()()) has maximum two levels of nesting while ((())) has three.

    >>> parse_nested_parens('(()()) ((())) () ((())()())')
    [2, 3, 1, 3]
    """
    depths = []
    if not paren_string:
        return depths

    groups = paren_string.split()
    for group in groups:
        pair_count = 0
        for char in group:
            if char == '(':
                pair_count += 1
            elif char == ')':
                pair_count -= 1
            if pair_count < 0:
                raise ValueError("Unbalanced parentheses")
        depths.append(pair_count)

    return depths
