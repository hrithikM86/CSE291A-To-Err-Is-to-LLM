def words_string(s: str) -> list[str]:
    # Replace commas with spaces
    s = s.replace(',', ' ')
    # Split the string by whitespace and filter out any empty strings
    words = [word for word in s.split() if word]
    return words
