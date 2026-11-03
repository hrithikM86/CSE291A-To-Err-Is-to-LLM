def pluck(arr):
    smallest_even_value = float('inf')
    smallest_index = -1

    for i, value in enumerate(arr):
        if value % 2 == 0 and value <= smallest_even_value:
            if value < smallest_even_value or smallest_index == -1:
                smallest_even_value = value
                smallest_index = i

    if smallest_index == -1:
        return []
    else:
        return [smallest_even_value, smallest_index]
