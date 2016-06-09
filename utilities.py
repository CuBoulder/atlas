"""utilities.py

    Modular utility functions for Atlas.

"""
import ldap
import sys

path = '/data/code'
if path not in sys.path:
    sys.path.append(path)

from atlas.config import ldap_server, ldap_org_unit, ldap_dns_domain_name

"""
    Connects to LDAP and tries to bind as the user.

    :param username: username
    :param password: the password associated with the username
"""
def check_ldap_credentials(username, password):

    # Initialize LDAP.
    # The initialize() method returns an LDAPObject object, which contains
    # methods for performing LDAP operations and retrieving information about
    # the LDAP connection and transactions.
    l = ldap.initialize(ldap_server)

    # Start the connection in a secure manner. Catch any errors and print the
    # description if present.
    try:
        l.start_tls_s()
    except ldap.LDAPError, e:
        print e.message['info']
        if type(e.message) == dict and e.message.has_key('desc'):
            print e.message['desc']
        else:
            print e

    ldap_distinguished_name = "uid={0},ou={1},{2}".format(username,ldap_org_unit,ldap_dns_domain_name)
    print ldap_distinguished_name

    try:
        # Try a synchronous bind (we want synchronous so that the command is
        # blocked until the bind gets a result. If you can bind, the
        # credentials are valid.
        result = l.simple_bind_s(ldap_distinguished_name, password)
        return True
    except ldap.INVALID_CREDENTIALS:
        print "Username or Password is incorrect."

    # Apparently this was a bad login attempt
    return False