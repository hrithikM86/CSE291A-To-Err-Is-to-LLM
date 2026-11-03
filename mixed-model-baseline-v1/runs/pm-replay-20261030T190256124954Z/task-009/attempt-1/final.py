from typing import List

def rolling_max(numbers: List[int]) -> List[int]:
    """
    From a given list of integers, generate a list of rolling maximum element found until given moment
    in the sequence.
    >>> rolling_max([1, 2, 3, 2, 3, 4, 2])
    [1, 2, 3, 3, 3, 4, 4]
    """
    if not numbers:
        return []
    if len(numbers) == 1:
        return numbers

    rolling_max_values = []
    current_max = float('-inf')

    for i in range(len(numbers)):
        current_max = max(current_max, numbers[i])
        rolling_max_values.append(current_max)

    return rolling_max_values
