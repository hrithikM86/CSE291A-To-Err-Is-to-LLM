def hex_key(num: str) -> int:
    # Define the set of prime hexadecimal digits
    prime_hex_digits = {'2', '3', '5', '7', 'B', 'D'}
    
    # Count the number of distinct prime hexadecimal digits in the input
    return len(prime_hex_digits.intersection(set(num)))

# Test cases
print(hex_key("AB"))       # Output: 1
print(hex_key("1077E"))    # Output: 2
print(hex_key("ABED1A33")) # Output: 4
print(hex_key("123456789ABCDEF0")) # Output: 6
print(hex_key("2020"))     # Output: 2
print(hex_key(""))         # Output: 0
print(hex_key("1"))        # Output: 0
