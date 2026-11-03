def specialFilter(nums: list) -> int:
    def is_odd_digit(digit):
        return int(digit) % 2 != 0

    def is_valid_number(num):
        num_str = str(abs(num))
        return len(num_str) > 1 and is_odd_digit(num_str[0]) or is_odd_digit(num_str[-1])

    return sum(1 for num in nums if num > 10 and is_valid_number(num))
