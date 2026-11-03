def sort_even(l: list) -> list:
    if not l:
        return []

    even_elements = [l[i] for i in range(0, len(l), 2)]
    sorted_even_elements = sorted(even_elements)

    sorted_list = []
    even_index = 0
    for i in range(len(l)):
        if i % 2 == 0:
            sorted_list.append(sorted_even_elements[even_index])
            even_index += 1
        else:
            sorted_list.append(l[i])

    return sorted_list
