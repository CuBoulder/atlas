import sys
path = '/data/code'
if path not in sys.path:
    sys.path.append(path)
import ldap
import logging
import json
import datetime


from eve import Eve
from eve.auth import BasicAuth

from atlas.config import allowed_users, ldap_server, ldap_org_unit, ldap_dns_domain_name
from atlas.tasks import *

# Basic Authentication
class AtlasBasicAuth(BasicAuth):
    def check_auth(self, username, password, allowed_roles=['default'], resource='default', method='default'):
        if username not in allowed_users:
            return False

        # Test credentials against LDAP.
        # Initialize LDAP. The initialize() method returns an LDAPObject
        # object, which contains methods for performing LDAP operations and
        # retrieving information about the LDAP connection and transactions.
        l = ldap.initialize(ldap_server)

        # Start the connection in a secure manner. Catch any errors and print
        # the description if present.
        try:
            l.start_tls_s()
        except ldap.LDAPError, e:
            print e.message['info']
            if type(e.message) == dict and e.message.has_key('desc'):
                print e.message['desc']
            else:
                print e

        ldap_distinguished_name = "uid={0},ou={1},{2}".format(username, ldap_org_unit, ldap_dns_domain_name)

        try:
            # Try a synchronous bind (we want synchronous so that the
            # command is blocked until the bind gets a result. If you can
            # bind, the credentials are valid.
            result = l.simple_bind_s(ldap_distinguished_name, password)
            app.logger.info('LDAP - {0} - Bind successful'.format(username))
            return True
        except ldap.INVALID_CREDENTIALS:
            app.logger.info('LDAP - {0} - Invalid credentials'.format(username))
            print "Username or Password is incorrect."

        # Apparently this was a bad login attempt
        app.logger.info('LDAP - {0} - Bind failed'.format(username))
        return False

# TODO: Add in a message and/or result broker, I don't want to use the DB. It is currently 41 GB for inventory.

# Tell Eve to use Basic Auth where our data structure is defined.
app = Eve(auth=AtlasBasicAuth, settings="/data/code/atlas/config_data_structure.py")

# TODO: Remove debug mode.
app.debug = True

# Add specific callbacks for
#app.on_post_POST += sites_callback

if __name__ == '__main__':
    # Enable logging to file
    handler = logging.FileHandler('/var/log/celery/atlas.log')

    # The default log level is set to WARNING, so we have to explicitly set the
    # logging level to INFO.
    app.logger.setLevel(logging.INFO)
    # Append the handler to the default application logger
    app.logger.addHandler(handler)

    # This goes last
    app.run(host='0.0.0.0', ssl_context='adhoc')
