def add_elements(arr, k):
    sum = 0
    for i in range(k):
        if 0 <= arr[i] < 100:  # Check if the number has at most two digits
            sum += arr[i]
    return sum
