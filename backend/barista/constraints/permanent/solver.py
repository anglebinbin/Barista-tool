"""
This module defines permanent solver constraints.
"""
import os
import backend
from backend.barista.utils.logger import Log

logID = Log.getCallerId('constraints/solver')


def ensureSolverConstraints(solverDictionary):
    """Ensure that all constraints for the given solverDictionary are valid.

    Sets static values and removes invalid values.
    """

    # The file names inside of a session are static and must not be altered by the user
    if "net" not in solverDictionary or solverDictionary["net"] != backend.barista.session.session_utils.Paths.FILE_NAME_NET_INTERNAL:
        Log.log("The solver property 'net' must point to the generated network file. "
                "Value has been changed from '{}' to '{}'.".format(
            solverDictionary["net"] if "net" in solverDictionary else "None",
            backend.barista.session.session_utils.Paths.FILE_NAME_NET_INTERNAL
        ), logID)
        solverDictionary["net"] = backend.barista.session.session_utils.Paths.FILE_NAME_NET_INTERNAL

    # An additional net definition inside of the solver would be inconsistent to the separately handled network
    if "net_param" in solverDictionary:
        Log.log("The solver property 'net_param' is not supported as it would be inconsistent with the separately "
                "handled network. Property has been removed.", logID)
        del solverDictionary["net_param"]

    # a snapshot_prefix containing a path is not supported either
    if "snapshot_prefix" in solverDictionary:
        head, tail = os.path.split(solverDictionary["snapshot_prefix"])

        if len(head) > 0:
            Log.log("The solver property 'snapshot_prefix' contained an unsupported path. "
                    "Property was shortened from '{}' to '{}'.".format(
                solverDictionary["snapshot_prefix"],
                tail
            ), logID)
            solverDictionary["snapshot_prefix"] = tail

    return solverDictionary
