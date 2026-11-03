def can_arrange(arr):
    # Check if the array is empty
    if not arr:
        return -1
    # Check if the array has only one element
    if len(arr) == 1:
        return -1
    
    # Traverse the list from the second last element to the first element
    for i in range(len(arr) - 1, 0, -1):
        # Compare the current element with the previous element
        if arr[i] < arr[i - 1]:
            return i
    
    # If no such element is found, return -1
    return -1
