def do_algebra(operator, operand):
    """
    Given two lists operator, and operand. The first list has basic algebra operations, and 
    the second list is a list of integers. Use the two given lists to build the algebric 
    expression and return the evaluation of this expression.

    The basic algebra operations:
    Addition ( + ) 
    Subtraction ( - ) 
    Multiplication ( * ) 
    Floor division ( // ) 
    Exponentiation ( ** ) 

    Example:
    operator['+', '*', '-']
    array = [2, 3, 4, 5]
    result = 2 + 3 * 4 - 5
    => result = 9

    Note:
        The length of operator list is equal to the length of operand list minus one.
        Operand is a list of non-negative integers.
        Operator list has at least one operator, and operand list has at least two operands.
    """

    if not operator or not operand:
        raise ValueError("Both operator and operand lists must not be empty.")
    if len(operator) != len(operand) - 1:
        raise ValueError("The length of operator list must be equal to the length of operand list minus one.")
    if len(operand) < 2:
        raise ValueError("Operand list must contain at least two elements.")
    if len(operator) < 1:
        raise ValueError("Operator list must have at least one operator.")

    valid_operators = {'+', '-', '*', '//', '**'}
    if not all(op in valid_operators for op in operator):
        raise ValueError("All operators must be one of '+', '-', '*', '//', '**'.")
    
    result = operand[0]
    for i, op in enumerate(operator):
        if op == '+':
            result += operand[i + 1]
        elif op == '-':
            result -= operand[i + 1]
        elif op == '*':
            result *= operand[i + 1]
        elif op == '//':
            if operand[i + 1] == 0:
                raise ValueError("Division by zero is not allowed.")
            result //= operand[i + 1]
        elif op == '**':
            result **= operand[i + 1]
    
    return result
