"""
This subpackage contains all constraints that need to be ensured permanently.
So the given methods need to be called each time one of the handled constraints might get broken, which is usually
identically to all situations in which the user could edit the raw prototxt file or equivalent data (as in the project
file).
"""