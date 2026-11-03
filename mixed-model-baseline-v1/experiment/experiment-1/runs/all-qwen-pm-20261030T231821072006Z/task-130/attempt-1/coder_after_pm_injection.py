def tri(n: int) -> list:
    if n < 0:
        raise ValueError("n must be a non-negative integer")
    
    if n == 0:
        return [1]
    elif n == 1:
        return [1, 3]
    
    sequence = [1, 3]
    for i in range(2, n + 1):
        if i % 2 == 0:
            sequence.append(1 + i // 2)
        else:
            sequence.append(sequence[-1] + sequence[-2] + sequence[0])
    
    return sequence[:n + 1]
