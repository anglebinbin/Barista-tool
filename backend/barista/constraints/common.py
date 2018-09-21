"""Common (helper) functions to check constraints."""


def isNumber(input):
    """Check whether input is a valid (float) number."""
    try:
        float(input)
        return True
    except ValueError:
        return False

def isPositiveNumber(input):
    """Check whether input is a valid (float) number > 0."""
    return isNumber(input) and input > 0

def isPositiveInteger(input):
    """Check whether input is a valid integer > 0."""
    return isPositiveNumber(input) and float(input).is_integer()