def compare(game, guess):
    if not isinstance(game, list) or not isinstance(guess, list):
        raise ValueError("Both game and guess must be lists.")
    if len(game) != len(guess):
        raise ValueError("Both lists must be of equal length.")
    
    result = []
    for i in range(len(game)):
        diff = abs(game[i] - guess[i])
        result.append(diff)
    
    return result
