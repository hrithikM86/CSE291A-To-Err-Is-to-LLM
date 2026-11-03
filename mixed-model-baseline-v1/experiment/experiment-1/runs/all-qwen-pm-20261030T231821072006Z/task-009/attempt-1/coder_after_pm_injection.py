from typing import List

def rolling_max(numbers: List[int]) -> List[int]:
    if not numbers:
        return []
    
    if len(numbers) == 1:
        return numbers
    
    rolling_max_values = [numbers[0]]
    current_max = numbers[0]
    
    for i in range(1, len(numbers)):
        current_max = max(current_max, numbers[i-1], numbers[i])
        rolling_max_values.append(current_max)
    
    return rolling_max_values
