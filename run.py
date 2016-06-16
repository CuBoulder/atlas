import sys
path = '/data/code'
if path not in sys.path:
    sys.path.append(path)
import logging
import json
import datetime


from eve import Eve
from eve.auth import BasicAuth

from atlas.utilities import check_ldap_credentials
from atlas.config import allowed_users
from atlas.tasks import *

# Basic Authentication
class AtlasBasicAuth(BasicAuth):
    def check_auth(self, username, password, allowed_roles=['default'], resource='default', method='default'):
        if username not in allowed_users:
            return False
        # Test credentials against LDAP.
        return check_ldap_credentials(username, password)

# TODO: Add in a message and/or result broker, I don't want to use the DB.
#   It is currently 41 GB for inventory.
# Tell Eve to use Basic Auth where our data structure is defined.
app = Eve(auth=AtlasBasicAuth, settings="/data/code/atlas/config_data_structure.py")
# TODO: Remove debug mode.
app.debug = True

# Add specific callbacks for
#app.on_post_POST += sites_callback

if __name__ == '__main__':
    app.run(host='0.0.0.0', ssl_context='adhoc')
    # enable logging to 'app.log' file
    handler = logging.FileHandler('/var/log/celery/atlas.log')
    # the default log level is set to WARNING, so we have to explicitly set the
    # logging level to INFO.
    app.logger.setLevel(logging.INFO)
    # append the handler to the default application logger
    app.logger.addHandler(handler)
