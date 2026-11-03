def same_chars(s0: str, s1: str) -> bool:
    # Lowercase both strings and remove spaces
    s0 = s0.replace(" ", "").lower()
    s1 = s1.replace(" ", "").lower()

    # Check if the lengths of the processed strings are different
    if len(s0) != len(s1):
        return False

    # Create sets from each string to remove duplicates and ignore order
    set_s0 = set(s0)
    set_s1 = set(s1)

    # Compare the two sets for equality
    return set_s0 == set_s1
