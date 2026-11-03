def count_distinct_characters(string: str) -> int:
    if not string:
        return 0
    
    distinct_chars = set(string)
    return len(distinct_chars)

# Test cases
assert count_distinct_characters('xyzXYZ') == 6
assert count_distinct_characters('Jerry') == 4
assert count_distinct_characters('') == 0
assert count_distinct_characters(' ') == 0
assert count_distinct_characters('aaaaa') == 1
