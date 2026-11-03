def valid_date(date: str) -> bool:
    if not date:
        return False
    
    try:
        month, day, year = date.split('-')
        month = int(month)
        day = int(day)
        year = int(year)
    except ValueError:
        return False
    
    if month < 1 or month > 12:
        return False
    
    if day < 1 or day > 31:
        return False
    
    return True
