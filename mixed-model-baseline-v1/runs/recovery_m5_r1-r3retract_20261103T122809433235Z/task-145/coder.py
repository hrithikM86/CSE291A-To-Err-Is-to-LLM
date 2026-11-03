def order_by_points(nums: list) -> list:
    def digit_sum(n: int) -> int:
        return sum(int(digit) for digit in str(abs(n)))

    if not nums:
        return []

    indexed_nums = [(index, digit_sum(num), num) for index, num in enumerate(nums)]
    sorted_nums = sorted(indexed_nums, key=lambda x: (x[1], x[0]))
    return [num for _, _, num in sorted_nums]
