def get_positive(l: list) -> list:
    """
    Return only positive numbers in the list.
    >>> get_positive([-1, 2, -4, 5, 6])
    [2, 5, 6]
    >>> get_positive([5, 3, -5, 2, -3, 3, 9, 0, 123, 1, -10])
    [5, 3, 2, 3, 9, 123, 1]
    """
    # Initialize an empty list to store positive numbers
    positive_nums = []
    
    # Iterate through each number in the input list
    for num in l:
        # Check if the number is positive
        if num > 0:
            # Append the number to the positive_nums list
            positive_nums.append(num)
    
    # Return the list of positive numbers
    return positive_nums
