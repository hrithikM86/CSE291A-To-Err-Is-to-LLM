def rounded_avg(n: int, m: int) -> str or int:
    if n <= 0 or m <= 0:
        raise ValueError("Both n and m must be positive integers.")
    if n > m:
        return -1

    sum = (n + m) * (m - n + 1) // 2
    count = m - n + 1
    average = sum // count

    # Handle halfway case by rounding to the nearest even integer
    if sum % count == count // 2:
        average += average % 2

    return bin(average)
