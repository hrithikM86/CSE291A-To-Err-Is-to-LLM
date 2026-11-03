import heapq

def minPath(grid, k):
    N = len(grid)
    if N < 2 or k < 1:
        raise ValueError("Grid must be at least 2x2 and k must be a positive integer")
    
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    pq = []
    
    for i in range(N):
        for j in range(N):
            heapq.heappush(pq, ((grid[i][j],), i, j))
    
    while pq:
        path, x, y = heapq.heappop(pq)
        if len(path) == k:
            return list(path)
        
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if 0 <= nx < N and 0 <= ny < N:
                heapq.heappush(pq, ((path + (grid[nx][ny],), nx, ny)))
    
    return []
