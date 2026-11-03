def unique(l: list) -> list:
    if not l:
        return []
    return sorted(set(l))
