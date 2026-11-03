def by_length(arr):
    digit_names = {
        1: "One",
        2: "Two",
        3: "Three",
        4: "Four",
        5: "Five",
        6: "Six",
        7: "Seven",
        8: "Eight",
        9: "Nine"
    }

    valid_digits = [num for num in arr if 1 <= num <= 9]
    valid_digits.sort()
    valid_digits.reverse()

    result = [digit_names[num] for num in valid_digits]

    return result
