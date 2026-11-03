from typing import List

def rolling_max(numbers: List[int]) -> List[int]:
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
