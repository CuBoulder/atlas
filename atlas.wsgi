import sys
path = '/data/code'
if path not in sys.path:
    sys.path.append(path)
from atlas.run import app as application
