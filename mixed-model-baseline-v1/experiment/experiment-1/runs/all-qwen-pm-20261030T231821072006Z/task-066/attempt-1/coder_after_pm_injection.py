def digitSum(s: str) -> int:
    total = 0
    for char in s:
        if 'A' <= char <= 'Z':
            total += ord(char) - ord('A') + 1
    return total
