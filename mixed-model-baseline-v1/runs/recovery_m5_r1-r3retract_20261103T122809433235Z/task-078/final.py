def hex_key(num: str) -> int:
    prime_hex = {'2', '3', '5', '7', 'B', 'D'}
    count = 0
    for c in num:
        if c in prime_hex:
            count += 1
    return count
