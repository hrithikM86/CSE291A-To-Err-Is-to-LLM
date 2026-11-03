def minSubArraySum(nums: list) -> int:
    if not nums:
        raise ValueError("Input list cannot be empty")
    if len(nums) == 1:
        return nums[0]
    
    min_sum = nums[0]
    current_sum = 0
    
    for num in nums:
        current_sum += num
        if current_sum < min_sum:
            min_sum = current_sum
        if current_sum < 0:
            current_sum = 0
    
    return min_sum
