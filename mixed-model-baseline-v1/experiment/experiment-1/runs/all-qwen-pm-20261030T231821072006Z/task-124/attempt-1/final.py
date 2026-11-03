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

    # Check for months with 30 days
    if month in [4, 6, 9, 11] and day > 30:
        return False

    # Check for February
    if month == 2:
        if day > 29:
            return False
        # Check for leap year
        if day == 29 and not (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
            return False

    return True
