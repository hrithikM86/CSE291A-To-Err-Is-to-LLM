def exchange(lst1, lst2):
    # Check if lst1 is already all even
    if all(x % 2 == 0 for x in lst1):
        return "YES"
    
    # Check if lst2 has no even entries
    if all(x % 2 != 0 for x in lst2):
        return "NO"
    
    # Count odd entries in lst1 and even entries in lst2
    odd_count_lst1 = sum(1 for x in lst1 if x % 2 != 0)
    even_count_lst2 = sum(1 for x in lst2 if x % 2 == 0)
    
    # Return "YES" only when the counts are equal
    return "YES" if odd_count_lst1 <= even_count_lst2 else "NO"
