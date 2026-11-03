def pluck(arr):
    """
    Given an array representing a branch of a tree that has non-negative integer nodes
    your task is to pluck one of the nodes and return it.
    The plucked node should be the node with the smallest even value.
    If multiple nodes with the same smallest even value are found return the node that has smallest index.

    The plucked node should be returned in a list, [smallest_value, its index],
    If there are no even values or the given array is empty, return [].
    """
    smallest_even = float('inf')
    smallest_index = -1

    for index, value in enumerate(arr):
        if value % 2 == 0 and value <= smallest_even:
            smallest_even = value
            smallest_index = index

    return [smallest_even, smallest_index] if smallest_index != -1 else []
