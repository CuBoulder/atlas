"""
Utility functions.
"""
import sys
import requests
import ldap
import json

from cryptography.fernet import Fernet
from random import choice
from string import lowercase
from hashlib import sha1
from eve.auth import BasicAuth
from flask import current_app
from atlas.config import *

path = '/data/code'
if path not in sys.path:
    sys.path.append(path)


class AtlasBasicAuth(BasicAuth):
    """
    Basic Authentication
    """
    def check_auth(self, username, password, allowed_roles=['default'], resource='default', method='default'):
        # Check if username is in 'allowed users' defined in config_local.py
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
            current_app.logger.error(e.message['info'])
            if type(e.message) == dict and e.message.has_key('desc'):
                current_app.logger.error(e.message['desc'])
            else:
                current_app.logger.error(e)

        ldap_distinguished_name = "uid={0},ou={1},{2}".format(username, ldap_org_unit, ldap_dns_domain_name)
        current_app.logger.debug(ldap_distinguished_name)

        try:
            # Try a synchronous bind (we want synchronous so that the command
            # is blocked until the bind gets a result. If you can bind, the
            # credentials are valid.
            result = l.simple_bind_s(ldap_distinguished_name, password)
            current_app.logger.debug('LDAP - {0} - Bind successful'.format(username))
            return True
        except ldap.INVALID_CREDENTIALS:
            current_app.logger.debug('LDAP - {0} - Invalid credentials'.format(username))

        # Apparently this was a bad login attempt
        current_app.logger.info('LDAP - {0} - Bind failed'.format(username))
        return False


def randomstring(length=14):
    """
    :param length: Length of the string
    :return: String of random lowercase letters.
    """
    return ''.join(choice(lowercase) for i in range(length))


def mysql_password():
    """
    Hash string twice with SHA1 and return uppercase hex digest, prepended with
    an astrix.

    This function is identical to the MySQL PASSWORD() function.
    """
    start = randomstring()
    pass1 = sha1(start).digest()
    pass2 = sha1(pass1).hexdigest()
    return "*" + pass2.upper()


# See https://cryptography.io/en/latest/fernet/#implementation
def encrypt_string(string):
    cipher = Fernet(encryption_key)
    msg = cipher.encrypt(string)
    encrypted = msg.encode('hex')
    return encrypted


def decrypt_string(string):
    cipher = Fernet(encryption_key)
    msg = string.decode('hex')
    decrypted = cipher.decrypt(msg)
    return decrypted


def get_eve(resource, query):
    """
    Make calls to the Atlas API.

    :param resource:
    :param query: argument string
    :return: dict of items that match the query string.
    """
    url = "{0}/{1}?{2}".format(api_server, resource, query)
    current_app.logger.debug('query_eve URL - {0}'.format(url))
    r = requests.get(url, auth=(ldap_username, ldap_password), verify=False)
    if r.ok:
        return r.json()
    else:
        return r.text

def patch_eve(resource, item, etag, request_payload):
    """
    Patch items in the Atlas API.

    :param resource:
    :param item:
    :param request_payload:
    :return:
    """
    url = "{0}/{1}/{2}".format(api_server, resource, item)
    current_app.logger.debug('patch_eve URL - {0}'.format(url))
    headers = {'Content-Type': 'application/json', 'If-Match': etag}
    r = requests.patch(url, headers=headers, data=json.dumps(request_payload), auth=(ldap_username, ldap_password))
    if r.ok:
        return r.json()
    else:
        return r.text
