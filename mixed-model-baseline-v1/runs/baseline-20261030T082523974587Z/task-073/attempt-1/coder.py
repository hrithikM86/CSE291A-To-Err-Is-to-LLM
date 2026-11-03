def smallest_change(arr):
    n = len(arr)
    changes = 0
    left = 0
    right = n - 1
    
    while left < right:
        if arr[left] != arr[right]:
            changes += 1
        left += 1
        right -= 1
    
    return changes
