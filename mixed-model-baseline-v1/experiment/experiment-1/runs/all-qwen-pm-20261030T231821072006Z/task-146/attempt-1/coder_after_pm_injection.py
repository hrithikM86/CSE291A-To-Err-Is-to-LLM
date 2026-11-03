def specialFilter(nums: list) -> int:
    def is_odd_digit(n):
        while n > 0:
            last_digit = n % 10
            if last_digit % 2 != 0:
                return True
            n //= 10
        return False
    
    count = 0
    for num in nums:
        if num > 10:
            if is_odd_digit(abs(num)) or is_odd_digit(abs(num) // 10):
                count += 1
    return count
