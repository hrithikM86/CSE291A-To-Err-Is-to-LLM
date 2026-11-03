from typing import List

def parse_music(music_string: str) -> List[int]:
    """
    Input to this function is a string representing musical notes in a special ASCII format.
    Your task is to parse this string and return list of integers corresponding to how many beats does each
    note last.

    Here is a legend:
    'o' - whole note, lasts four beats
    'o|' - half note, lasts two beats
    '.|' - quarter note, lasts one beat

    >>> parse_music('o o| .| o| o| .| .| .| .| o o')
    [4, 2, 1, 2, 2, 1, 1, 1, 1, 4, 4]
    """
    durations = []
    i = 0
    while i < len(music_string):
        if music_string[i] == 'o':
            durations.append(4)
            i += 1
        elif music_string[i:i+2] == 'o|':
            durations.append(2)
            i += 2
        elif music_string[i:i+2] == '.|':
            durations.append(1)
            i += 2
        else:
            i += 1
    return durations
