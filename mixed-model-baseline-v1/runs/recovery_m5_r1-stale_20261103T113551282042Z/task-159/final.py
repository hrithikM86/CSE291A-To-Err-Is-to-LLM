from typing import List

def eat(number: int, need: int, remaining: int) -> List[int]:
    total_eaten = number + min(need, remaining)
    remaining_stock = max(remaining - need, 0)
    return [total_eaten, remaining_stock]
