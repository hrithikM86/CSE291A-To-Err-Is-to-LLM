def file_name_check(file_name: str) -> str:
    if not file_name:
        return 'No'
    
    if file_name.count('.') != 1:
        return 'No'
    
    prefix, suffix = file_name.split('.')
    
    if not prefix or not prefix[0].isalpha():
        return 'No'
    
    if suffix not in ['txt', 'exe', 'dll']:
        return 'No'
    
    if len([char for char in file_name if char.isdigit()]) > 3:
        return 'No'
    
    return 'Yes'
