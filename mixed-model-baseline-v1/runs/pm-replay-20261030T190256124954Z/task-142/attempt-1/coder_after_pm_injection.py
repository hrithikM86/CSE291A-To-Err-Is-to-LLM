def sum_squares(lst):
    total_sum = 0
    for i, x in enumerate(lst):
        if isinstance(x, int):
            if i % 4 == 0:
                total_sum += x ** 3
            elif i % 3 == 0:
                total_sum += x ** 2
            else:
                total_sum += x
    return total_sum
