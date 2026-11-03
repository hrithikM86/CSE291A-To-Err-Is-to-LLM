def check_if_last_char_is_a_letter(txt: str) -> bool:
    if not txt:
        return False

    last_char = txt[-1]
    second_last_char = txt[-2] if len(txt) > 1 else ''

    if not last_char.isalpha():
        return False

    if len(txt) > 1 and not second_last_char.isspace():
        return False

    return True
