def make_a_pile(n: int) -> list:
    """
    Given a positive integer n, you have to make a pile of n levels of stones.
    The first level has n stones.
    The number of stones in the next level is:
        - the next odd number if n is odd.
        - the next even number if n is even.
    Return the number of stones in each level in a list, where element at index
    i represents the number of stones in the level (i+1).

    Examples:
    >>> make_a_pile(3)
    [3, 5, 7]
    """
    if not isinstance(n, int) or n <= 0 or n > 1000:
        raise ValueError("n must be a positive integer within the range [1, 1000].")

    pile = []
    current_stones = n

    for _ in range(n):
        pile.append(current_stones)
        # Determine the next number of stones based on the parity of current_stones
        if current_stones % 2 == 0:
            current_stones += 2  # Next even number
        else:
            current_stones += 2  # Next odd number

    return pile
