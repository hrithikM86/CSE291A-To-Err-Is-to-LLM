def Strongest_Extension(class_name: str, extensions: list) -> str:
    if not class_name:
        return "Invalid class name"
    if not extensions:
        return class_name

    strongest_extension = None
    max_strength = -float('inf')

    for extension in extensions:
        cap = sum(1 for char in extension if char.isupper())
        sm = sum(1 for char in extension if char.islower())
        strength = cap - sm

        if strength > max_strength:
            max_strength = strength
            strongest_extension = extension
        elif strength == max_strength:
            # Choose the first one in the list if there are ties
            break

    return f"{class_name}.{strongest_extension}"
