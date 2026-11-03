def cycpattern_check(a: str, b: str) -> bool:
    """
    You are given 2 words. You need to return True if the second word or any of its rotations is a substring in the first word
    cycpattern_check("abcd","abd") => False
    cycpattern_check("hello","ell") => True
    cycpattern_check("whassup","psus") => False
    cycpattern_check("abab","baa") => True
    cycpattern_check("efef","eeff") => False
    cycpattern_check("himenss","simen") => True
    """
    # Step 1: Check for Empty Strings
    if not a or not b:
        return False

    # Step 3: Check for Substring
    return b in a
