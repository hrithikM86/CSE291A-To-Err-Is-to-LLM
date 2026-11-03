def sorted_list_sum(lst: list) -> list:
    # Step 1: Filter out strings with odd lengths
    filtered_list = [word for word in lst if len(word) % 2 == 0]
    
    # Step 2: Remove duplicates by converting to a set and back to a list
    unique_list = list(set(filtered_list))
    
    # Step 3: Sort the list by length, and alphabetically for strings of the same length
    sorted_list = sorted(unique_list, key=lambda x: (len(x), x))
    
    # Step 4: Return the sorted list
    return sorted_list
