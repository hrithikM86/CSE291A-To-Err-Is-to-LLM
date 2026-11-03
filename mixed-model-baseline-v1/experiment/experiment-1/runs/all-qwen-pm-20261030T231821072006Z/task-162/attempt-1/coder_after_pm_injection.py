import hashlib

def string_to_md5(text: str) -> str | None:
    """
    Given a string 'text', return its md5 hash equivalent string.
    If 'text' is an empty string, return None.
    """
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    
    if text == "":
        return None
    
    text = text.lower()
    md5_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
    return md5_hash
