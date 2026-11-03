from typing import List


def remove_duplicates(numbers: List[int]) -> List[int]:
    """
    From a list of integers, remove all elements that occur more than once.
    Keep order of elements left the same as in the input.
    >>> remove_duplicates([1, 2, 3, 2, 4])
    [1, 3, 4]
    """
    from collections import defaultdict

    seen = defaultdict(int)
    result = []

    for num in numbers:
        if seen[num] == 0:
            result.append(num)
        seen[num] += 1

    return result
