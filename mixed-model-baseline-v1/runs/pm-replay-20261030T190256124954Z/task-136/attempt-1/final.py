def largest_smallest_integers(lst):
    negative_values = [x for x in lst if x < 0]
    positive_values = [x for x in lst if x > 0]

    a = min(negative_values) if negative_values else None
    b = max(positive_values) if positive_values else None

    return (a, b)
