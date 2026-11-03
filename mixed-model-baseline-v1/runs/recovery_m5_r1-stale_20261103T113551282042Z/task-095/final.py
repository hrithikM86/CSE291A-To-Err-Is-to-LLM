def check_dict_case(dictionary):
    if not dictionary:
        return False

    lower_case = False
    upper_case = False

    for key in dictionary.keys():
        if not isinstance(key, str):
            return False
        if key.islower():
            lower_case = True
        elif key.isupper():
            upper_case = True
        else:
            return False

    return lower_case or upper_case
