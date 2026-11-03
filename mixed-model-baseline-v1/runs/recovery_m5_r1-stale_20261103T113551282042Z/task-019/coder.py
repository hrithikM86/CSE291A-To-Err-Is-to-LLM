from typing import List

def sort_numbers(numbers: str) -> str:
    number_map = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9}
    
    if not numbers:
        return ""
    
    number_words = numbers.split()
    valid_number_words = [word for word in number_words if word in number_map]
    
    if not valid_number_words:
        return ""
    
    numerical_values = [number_map[word] for word in valid_number_words]
    sorted_numerical_values = sorted(numerical_values)
    
    sorted_number_words = [list(number_map.keys())[list(number_map.values()).index(value)] for value in sorted_numerical_values]
    
    return " ".join(sorted_number_words)
