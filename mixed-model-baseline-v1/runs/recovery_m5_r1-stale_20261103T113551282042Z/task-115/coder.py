import math

def max_fill(grid, capacity):
    if not grid or not all(len(row) == len(grid[0]) for row in grid):
        raise ValueError("Invalid grid input")

    total_drops = 0
    total_water = sum(row.count(1) for row in grid)
    total_drops = math.ceil(total_water / capacity)

    return total_drops
