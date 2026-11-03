from typing import List

def intersperse(numbers: List[int], delimiter: int) -> List[int]:
    """ Insert a number 'delimiter' between every two consecutive elements of input list `numbers`
    >>> intersperse([], 4)
    []
    >>> intersperse([1, 2, 3], 4)
    [1, 4, 2, 4, 3]
    """
    if not numbers:
        return []
    
    result = []
    for number in numbers:
        result.append(number)
        result.append(delimiter)
    
    # Remove the trailing delimiter
    result.pop()
    
    return result
