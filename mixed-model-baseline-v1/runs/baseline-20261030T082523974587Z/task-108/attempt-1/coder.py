def count_nums(arr):
    count = 0
    for num in arr:
        if num == 0:
            continue
        digits = [int(d) for d in str(abs(num))]
        if num < 0:
            digits[0] = -digits[0]
        if sum(digits) > 0:
            count += 1
    return count
