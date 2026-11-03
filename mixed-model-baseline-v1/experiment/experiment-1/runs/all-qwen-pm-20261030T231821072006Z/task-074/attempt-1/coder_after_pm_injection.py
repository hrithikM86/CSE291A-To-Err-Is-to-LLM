def total_match(lst1, lst2):
    # If both lists are empty, return an empty list
    if not lst1 and not lst2:
        return []
    
    # If exactly one list is empty, return the non-empty list
    if not lst1:
        return lst2
    if not lst2:
        return lst1
    
    # Compare the number of elements in both lists
    if len(lst1) <= len(lst2):
        return lst1
    else:
        return lst2
