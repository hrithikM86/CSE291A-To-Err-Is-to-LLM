def is_prime(n: int) -> bool:
    if n <= 1:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True

def words_in_sentence(sentence: str) -> str:
    if not sentence:
        return ""
    
    words = sentence.split()
    prime_length_words = [word for word in words if is_prime(len(word))]
    
    if not prime_length_words:
        return ""
    
    return " ".join(prime_length_words)
