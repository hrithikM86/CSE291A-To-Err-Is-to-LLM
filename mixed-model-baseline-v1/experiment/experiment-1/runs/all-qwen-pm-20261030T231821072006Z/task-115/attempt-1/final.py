def max_fill(grid, capacity):
    import math

    if not grid:
        raise ValueError("Grid is empty")

    well_length = len(grid[0])
    for well in grid:
        if len(well) != well_length:
            raise ValueError("All wells must have the same length")

    total_water = sum(well.count(1) for well in grid)
    total_drops = math.ceil(total_water / capacity)

    return total_drops
