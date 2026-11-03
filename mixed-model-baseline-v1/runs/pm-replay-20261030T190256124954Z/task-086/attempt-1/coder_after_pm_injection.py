def anti_shuffle(s: str) -> str:
    words = s.split(' ')
    ordered_words = []
    for word in words:
        ordered_word = ''.join(sorted(word, reverse=True))
        ordered_words.append(ordered_word)
    return ' '.join(ordered_words)
