# Helper script to list dependencies for python modules. Can be used to find
# unnecessary dependencies in client.py and server.py and remove them one by one.

import sys
import argparse


if __name__ == '__main__':
    # Parse command line arguments.
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--module', help='Module to list imports for.', type=str, default='client')
    args = parser.parse_args()
    # Store modules before the import.
    before = [str(m) for m in sys.modules]
    # Import module.
    module = __import__(args.module)
    # Store modules which have added.
    after = [str(m) for m in sys.modules]
    print('\n'.join(sorted([m for m in after if not m in before])))
