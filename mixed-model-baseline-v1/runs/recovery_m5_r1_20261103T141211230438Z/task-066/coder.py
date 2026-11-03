def digitSum(s: str) -> int:
    sum = 0
    for c in s:
        if 'A' <= c <= 'Z':
            sum += ord(c)
    return sum
