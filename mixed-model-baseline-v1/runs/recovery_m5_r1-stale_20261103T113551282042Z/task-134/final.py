def check_if_last_char_is_a_letter(txt: str) -> bool:
    if not txt:
        return False
    if len(txt) == 1:
        return txt.isalpha()
    if txt[-1].isalpha() and not txt[-2].isalpha():
        return True
    return False
