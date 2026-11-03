def select_words(s: str, n: int) -> list:
    def count_consonants(word: str) -> int:
        consonants = "bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ"
        return sum(1 for char in word if char in consonants)

    if not s:
        return []

    words = s.split()
    result = [word for word in words if count_consonants(word) == n]

    return result
