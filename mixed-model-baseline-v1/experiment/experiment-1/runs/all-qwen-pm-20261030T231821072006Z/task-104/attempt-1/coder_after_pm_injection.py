def unique_digits(x: list) -> list:
    if not all(isinstance(i, int) and i > 0 for i in x):
        raise ValueError("All elements in the list must be positive integers.")
    
    def has_odd_digit(n):
        return any(int(digit) % 2 != 0 for digit in str(n))
    
    result = [num for num in x if has_odd_digit(num)]
    return sorted(result)

# Example usage:
print(unique_digits([15, 33, 1422, 1]))  # Output: [1, 15, 33]
print(unique_digits([152, 323, 1422, 10]))  # Output: []
