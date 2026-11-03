def odd_count(lst):
    result = []
    for s in lst:
        if not s:
            result.append("")
            continue
        even_count = sum(1 for char in s if int(char) % 2 == 0)
        output_string = f"the number of odd elements {even_count}n the str{even_count}ng {even_count} of the {even_count}nput."
        result.append(output_string)
    return result
