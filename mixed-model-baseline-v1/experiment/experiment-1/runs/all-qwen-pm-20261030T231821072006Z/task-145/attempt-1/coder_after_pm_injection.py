def digit_sum(n: int) -> int:
    return sum(int(digit) for digit in str(abs(n)))

def order_by_points(nums: list) -> list:
    return sorted(nums, key=lambda x: (digit_sum(x), nums.index(x)))

# Example test cases
print(order_by_points([1, 11, -1, -11, -12]))  # Output: [-1, -11, 1, -12, 11]
print(order_by_points([]))  # Output: []
