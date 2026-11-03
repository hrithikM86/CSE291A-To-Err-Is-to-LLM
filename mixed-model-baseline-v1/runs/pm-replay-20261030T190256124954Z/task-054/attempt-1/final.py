def same_chars(s0: str, s1: str) -> bool:
    # Lowercase both strings and remove spaces
    s0 = s0.replace(" ", "").lower()
    s1 = s1.replace(" ", "").lower()

    # Check if the lengths of the processed strings are different
    if len(s0) != len(s1):
        return False

    # Sort the character sequences with duplicate multiplicities
    sorted_s0 = sorted(s0)
    sorted_s1 = sorted(s1)

    # Compare the sorted sequences
    return sorted_s0 == sorted_s1
