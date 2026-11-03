def words_string(s: str) -> list[str]:
    if not s:
        return []
    
    # Normalize the string by replacing multiple commas or spaces with a single space
    s = ' '.join(s.replace(',', ' ').split())
    
    # Split the string by spaces and filter out any empty strings
    words = [word for word in s.split() if word]
    
    return words
