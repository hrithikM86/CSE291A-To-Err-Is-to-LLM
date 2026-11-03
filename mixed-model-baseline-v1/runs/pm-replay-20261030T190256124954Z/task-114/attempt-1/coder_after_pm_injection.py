def minSubArraySum(nums: list) -> int:
    if not nums:
        raise ValueError("Input list cannot be empty")
    if len(nums) == 1:
        return nums[0]
    
    min_sum = float('inf')
    for i in range(len(nums)):
        for j in range(i, min(i + 2, len(nums))):
            min_sum = min(min_sum, sum(nums[i:j]))
    
    return min_sum
