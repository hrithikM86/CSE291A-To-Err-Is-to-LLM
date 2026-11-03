def check_if_last_char_is_a_letter(txt: str) -> bool:
    if not txt:
        return False
    last_char = txt[-1]
    if not last_char.isspace():
        return last_char.isalpha()
    second_last_char = txt[-2] if len(txt) > 1 else ''
    return not second_last_char.isspace() and last_char.isalpha()
