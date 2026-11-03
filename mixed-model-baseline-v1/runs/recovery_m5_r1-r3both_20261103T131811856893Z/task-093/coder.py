def encode(message: str) -> str:
    vowels = 'aeiou'
    encoded_message = ''
    
    for char in message:
        if char.isalpha():
            swapped_char = char.swapcase()
            if swapped_char in vowels:
                index = (vowels.index(swapped_char.lower()) + 2) % len(vowels)
                new_char = vowels[index].upper() if swapped_char.isupper() else vowels[index]
                encoded_message += new_char
            else:
                encoded_message += swapped_char
        else:
            encoded_message += char
    
    return encoded_message
