def check_dict_case(dict):
    if not dict:
        return False

    lower_count = 0
    upper_count = 0
    key_count = len(dict)

    for key in dict.keys():
        if not isinstance(key, str):
            return False
        if key.islower():
            lower_count += 1
        elif key.isupper():
            upper_count += 1
        else:
            return False

    return lower_count == key_count or upper_count == key_count
