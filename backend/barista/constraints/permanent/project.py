"""
This module defines permanent constraints for a Barista project.
"""
from backend.barista.utils.logger import Log
from backend.barista.constraints.permanent.solver import ensureSolverConstraints

logID = Log.getCallerId('constraints/project')


def ensureProjectDataConstraints(projectData):
    """Take the current state of projectData and manipulate it to handle some special cases.

    This method should be called each time when the project data has been changed. It will adjust some values, which
    would be valid for the prototxt-syntax in general, but underlay further constraints especially for Barista.
    """
    if not hasattr(projectData, '__getItem__'):
        Log.error('Project data is empty.', logID)
        return projectData

    jsonKeys = ("activeSession", "environment", "inputdb", "projectid", "transform")
    keyNotFound = False
    for key in jsonKeys:
        if key not in projectData:
            Log.error("Project information is invalid! Key '"
                      + key + "' is missing!", logID)
            keyNotFound = True
    if keyNotFound:
        Log.error("Session at %s is invalid. Key %s in 'sessionstate.json' is missing", logID)

    # add further constraint types like e.g.:

    return projectData
