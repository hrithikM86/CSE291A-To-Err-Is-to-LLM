def order_by_points(nums: list) -> list:
    def digit_sum(n: int) -> int:
        return sum(int(digit) for digit in str(abs(n)))

    return sorted(nums, key=lambda x: (digit_sum(x), nums.index(x)))
