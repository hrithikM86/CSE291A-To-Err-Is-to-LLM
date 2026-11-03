def count_nums(arr):
    """
    Write a function count_nums which takes an array of integers and returns
    the number of elements which has a sum of digits > 0.
    If a number is negative, then its first signed digit will be negative:
    e.g. -123 has signed digits -1, 2, and 3.
    >>> count_nums([]) == 0
    >>> count_nums([-1, 11, -11]) == 1
    >>> count_nums([1, 1, 2]) == 3
    """
    if not arr:
        return 0

    count = 0
    for num in arr:
        # Compute the sum of digits of the absolute value of the number
        digit_sum = sum(int(digit) for digit in str(abs(num)))
        # Count the number if the sum of digits is positive
        if digit_sum > 0:
            count += 1

    return count
