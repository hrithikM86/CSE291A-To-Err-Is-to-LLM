from typing import List

def rescale_to_unit(numbers: List[float]) -> List[float]:
    if len(numbers) < 2:
        raise ValueError("The list must contain at least two elements.")
    
    min_value = min(numbers)
    max_value = max(numbers)
    
    if min_value == max_value:
        raise ValueError("The list must contain at least two different elements.")
    
    transformed_list = [(num - min_value) / (max_value - min_value) for num in numbers]
    return transformed_list
