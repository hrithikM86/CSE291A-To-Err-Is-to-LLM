def tri(n: int) -> list:
    if not isinstance(n, int) or n < 0:
        raise ValueError("Input must be a non-negative integer.")

    if n == 0:
        return [1]
    elif n == 1:
        return [1, 3]

    tribonacci_sequence = [1, 3]
    for i in range(2, n + 1):
        if i % 2 == 0:
            tribonacci_sequence.append(1 + i / 2)
        else:
            tribonacci_sequence.append(tribonacci_sequence[i-1] + tribonacci_sequence[i-2] + tribonacci_sequence[i+1])

    return tribonacci_sequence
