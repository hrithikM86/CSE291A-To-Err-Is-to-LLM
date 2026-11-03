def do_algebra(operator, operand):
    if not operator or not operand:
        raise ValueError("Both operator and operand lists must not be empty.")
    if len(operator) != len(operand) - 1:
        raise ValueError("The length of operator list must be equal to the length of operand list minus one.")
    if len(operand) < 2:
        raise ValueError("Operand list must contain at least two elements.")
    if len(operator) < 1:
        raise ValueError("Operator list must have at least one operator.")

    result = operand[0]

    for i in range(len(operator)):
        if operator[i] == '+':
            result += operand[i + 1]
        elif operator[i] == '-':
            result -= operand[i + 1]
        elif operator[i] == '*':
            result *= operand[i + 1]
        elif operator[i] == '//':
            if operand[i + 1] == 0:
                raise ValueError("Division by zero is not allowed.")
            result //= operand[i + 1]
        elif operator[i] == '**':
            result **= operand[i + 1]
        else:
            raise ValueError("Invalid operator. Only '+', '-', '*', '//', and '**' are allowed.")

    return result
