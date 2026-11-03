def solve(N: int) -> str:
    if not 0 <= N <= 10000:
        raise ValueError("N must be between 0 and 10000 inclusive.")
    
    if N == 0:
        return "0"
    
    sum_digits = 0
    for digit in str(N):
        sum_digits += int(digit)
    
    binary_sum = bin(sum_digits)[2:]  # Convert to binary and remove '0b' prefix
    return binary_sum
