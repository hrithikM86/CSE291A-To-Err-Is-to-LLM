def move_one_ball(arr):
    if len(arr) == 0:
        return True
    
    discontinuities = 0
    for i in range(len(arr)):
        if arr[i] > arr[(i + 1) % len(arr)]:
            discontinuities += 1
            if discontinuities > 1:
                return False
    return True
