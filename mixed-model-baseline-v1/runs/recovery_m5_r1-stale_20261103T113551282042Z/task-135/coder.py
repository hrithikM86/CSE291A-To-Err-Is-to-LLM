def can_arrange(arr):
    if not arr or len(arr) == 1:
        return -1
    
    for i in range(1, len(arr)):
        if arr[i] < arr[i-1]:
            return i
    
    return -1
