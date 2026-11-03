def by_length(arr):
    digit_names = ["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    valid_digits = [num for num in arr if 1 <= num <= 9]
    if not valid_digits:
        return []
    valid_digits.sort()
    valid_digits.reverse()
    result = [digit_names[num - 1] for num in valid_digits]
    return result
