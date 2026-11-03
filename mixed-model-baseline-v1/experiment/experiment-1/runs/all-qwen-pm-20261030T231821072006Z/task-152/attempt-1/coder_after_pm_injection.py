def compare(game, guess):
    # Function body
    if not isinstance(game, list) or not isinstance(guess, list):
        raise ValueError("Both game and guess must be lists.")
    if len(game) != len(guess):
        raise ValueError("game and guess must be of the same length.")
    
    result = []
    for i in range(len(game)):
        result.append(game[i] - guess[i])
    
    return result
