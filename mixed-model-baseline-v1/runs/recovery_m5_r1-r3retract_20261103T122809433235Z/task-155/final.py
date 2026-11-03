def even_odd_count(num: int) -> tuple:
    if num == 0:
        return (1, 0)
    
    if num < 0:
        num = -num
    
    even_count = 0
    odd_count = 0
    
    for char in str(num):
        if char.isdigit():
            digit = int(char)
            if digit % 2 == 0:
                even_count += 1
            else:
                odd_count += 1
    
    return (even_count, odd_count)
