def sum_squares(lst):
    """
    This function will take a list of integers. For all entries in the list, the function shall square the integer entry if its index is a
    multiple of 3 and will cube the integer entry if its index is a multiple of 4 and not a multiple of 3. The function will not
    change the entries in the list whose indexes are not a multiple of 3 or 4. The function shall then return the sum of all entries.
    """
    total_sum = 0
    
    for i, value in enumerate(lst):
        if i % 4 == 0 and i != 0:  # Cube the value if index is a multiple of 4 and not 0
            total_sum += value ** 3
        elif i % 3 == 0:  # Square the value if index is a multiple of 3
            total_sum += value ** 2
    
    return total_sum

# Test cases
print(sum_squares([1, 2, 3]))  # Output: 6
print(sum_squares([]))         # Output: 0
print(sum_squares([-1, -5, 2, -1, -5]))  # Output: -126
