def encode(message: str) -> str:
    vowels = 'aeiou'
    shifted_vowels = {v: chr((ord(v) - ord('a') + 2) % 26 + ord('a')) for v in vowels}
    shifted_vowels.update({v.upper(): chr((ord(v.upper()) - ord('A') + 2) % 26 + ord('A')) for v in vowels})
    
    encoded_message = []
    for char in message:
        if char.isalpha():
            if char.lower() in vowels:
                new_char = shifted_vowels[char.lower()]
            else:
                new_char = char
            encoded_message.append(new_char.swapcase())
        else:
            encoded_message.append(char)
    
    return ''.join(encoded_message)
