import hashlib
import os

def hashFile(path):
    """Hashes a file and returns the hashvalue"""
    m = hashlib.md5()
    try:
        file = open(path, "r")
        for chunk in iter(lambda: file.read(4096), b""):
            m.update(chunk)
        return m.hexdigest()
    except Exception as e:
        print e
        exit -1

def hashDir(path):
    """Hashes a directory and returns the hashvalue"""
    hash = ""

    for root, dirs, files in os.walk(path):
        for names in sorted(files):
            try:
                filepath = os.path.join(root, names)
                hash += hashFile(filepath)
            except Exception as e:
                print e
                exit -1

    return hash