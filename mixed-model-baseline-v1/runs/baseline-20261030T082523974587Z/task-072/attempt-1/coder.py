def will_it_fly(q, w):
    if not q:  # Step 1
        return False
    n = len(q)
    for i in range(n // 2):  # Step 2
        if q[i] != q[n - 1 - i]:
            return False
    total_sum = sum(q)  # Step 3
    return total_sum <= w  # Step 4
