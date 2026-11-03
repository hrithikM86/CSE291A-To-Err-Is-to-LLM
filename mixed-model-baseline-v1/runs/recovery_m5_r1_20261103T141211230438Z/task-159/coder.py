from typing import List

def eat(number: int, need: int, remaining: int) -> List[int]:
    total_eaten = number
    if remaining == 0:
        total_eaten += need
        remaining = 0
    elif need > 0:
        to_eat = min(need, remaining)
        total_eaten += to_eat
        remaining -= to_eat
    return [total_eaten, remaining]
