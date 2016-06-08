import sys
path = '/data/code'
if path not in sys.path:
    sys.path.append(path)
import logging
import json
import datetime

from eve import Eve
from hashlib import sha1

from atlas import tasks

app = Eve(settings="/data/code/atlas/settings_data_structure.py")

if __name__ == '__main__':
    app.run(host='0.0.0.0', ssl_context='adhoc')
    # enable logging to 'app.log' file
    handler = logging.FileHandler('/var/log/celery/atlas.log')

    # the default log level is set to WARNING, so we have to explicitly set the
    # logging level to INFO.
    app.logger.setLevel(logging.INFO)
    # append the handler to the default application logger
    app.logger.addHandler(handler)
