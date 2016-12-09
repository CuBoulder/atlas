"""
Utility functions.
"""
import sys
import requests
import ldap
import json

from base64 import b64encode
from re import compile, search
from cryptography.fernet import Fernet
from random import choice
from string import lowercase
from hashlib import sha1
from eve.auth import BasicAuth
from flask import current_app as app
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
            app.logger.error(e.message['info'])
            if type(e.message) == dict and e.message.has_key('desc'):
                app.logger.error(e.message['desc'])
            else:
                app.logger.error(e)

        ldap_distinguished_name = "uid={0},ou={1},{2}".format(username, ldap_org_unit, ldap_dns_domain_name)
        app.logger.debug(ldap_distinguished_name)

        try:
            # Try a synchronous bind (we want synchronous so that the command
            # is blocked until the bind gets a result. If you can bind, the
            # credentials are valid.
            result = l.simple_bind_s(ldap_distinguished_name, password)
            app.logger.debug('LDAP - {0} - Bind successful'.format(username))
            return True
        except ldap.INVALID_CREDENTIALS:
            app.logger.debug('LDAP - {0} - Invalid credentials'.format(username))

        # Apparently this was a bad login attempt
        app.logger.info('LDAP - {0} - Bind failed'.format(username))
        return False

def basic_auth_header(username=ldap_username, password=ldap_password):
    return 'Basic ' + b64encode(username + ":" + password)


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


def post_eve(resource, payload):
    """
    Make calls to the Atlas API.

    :param resource: A resource as defined in config_data_structure.py
    :param payload: argument string
    """
    url = "{0}/{1}".format(api_urls[environment], resource)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': basic_auth_header()
    }
    r = app.test_client().post(url, headers=headers, data=json.dumps(payload))
    app.logger.debug(r.data)

    result = r.data

    if r._status_code == 200:
        result = json.loads(r.data)

    return result


def get_eve(resource, query, single=False):
    """
    Make calls to the Atlas API.

    :param resource: Atlas endpoint to access
    :param query: argument string
    :param single: boolean - True if requesting a single items
    :return: dict of items that match the query string.
    """

    url = "{0}/{1}?where{2}".format(api_urls[environment], resource, query)
    if single:
        url = "{0}/{1}/{2}".format(api_urls[environment], resource, query)
    app.logger.debug(url)

    r = app.test_client().get(url)
    app.logger.debug(r.data)

    result = r.data

    if r._status_code == 200:
        result = json.loads(r.data)

    return result


def patch_eve(resource, id, request_payload):
    """
    Patch items in the Atlas API.

    :param resource:
    :param id:
    :param request_payload:
    :return:
    """
    url = "{0}/{1}/{2}".format(api_urls[environment], resource, id)
    get_etag = get_eve(resource, id, True)
    headers = {
        'Content-Type': 'application/json',
        'If-Match': get_etag['_etag'],
        'Authorization': basic_auth_header()
    }
    r = app.test_client().patch(url, headers=headers, data=json.dumps(request_payload))
    app.logger.debug(r.data)

    result = r.data

    if r._status_code == 200:
        result = json.loads(r.data)

    return result


def delete_eve(resource, id):
    """
    Patch items in the Atlas API.

    :param resource:
    :param id:
    :return:
    """
    url = "{0}/{1}/{2}".format(api_urls[environment], resource, id)
    get_etag = get_eve(resource, id, True)
    headers = {
        'Content-Type': 'application/json',
        'If-Match': get_etag['_etag'],
        'Authorization': basic_auth_header()
    }
    r = app.test_client().delete(url, headers=headers, data=json.dumps(request_payload))
    app.logger.debug(r.data)

    result = r.data

    if r._status_code == 200:
        result = json.loads(r.data)

    return result


def get_current_code(name, type):
    """
    Get the current code item for a given name and type.

    :param name: string
    :param type: string
    :return: _id of the item.
    """
    query = 'where={{"meta.name":"{0}","meta.code_type":"{1}","meta.is_current":true}}'.format(name, type)
    current_get = get_eve('code', query)
    print(current_get)
    return current_get['_items'][0]['_id']


def get_code(name, code_type=''):
    """
    Get the current code item for a given name and code_type.

    :param name: string
    :param code_type: string
    :return: _id of the item.
    """
    if code_type:
        query = 'where={{"meta.name":"{0}","meta.code_type":"{1}"}}'.format(
            name,
            code_type)
    else:
        query = 'where={{"meta.name":"{0}"}}'.format(name)
    code_get = get_eve('code', query)
    print(code_get)
    return code_get


def import_code(query):
    """
    Import code definitions from a URL. Should be a JSON file export from Atlas
     or a live Atlas code endpoint.

    :param query: URL for JSON to import
    """
    r = requests.get(query)
    print(r.json())
    data = r.json()
    for code in data['_items']:
        payload = {
            'git_url': code['git_url'],
            'commit_hash': code['commit_hash'],
            'meta': {
                'name': code['meta']['name'],
                'version': code['meta']['version'],
                'code_type': code['meta']['code_type'],
                'is_current': code['meta']['is_current'],
            },
        }
        if code['meta'].get('tag'):
            payload['meta']['tag'] = code['meta']['tag']
        post_eve('code', payload)


def post_to_slack(message, title, link='', attachment_text='', level='good', user=slack_username):
    """
    Posts a message to a given channel using the Slack Incoming Webhooks API.
    Links should be in the message or attachment_text in the format:
    `<https://www.colorado.edu/p1234|New Website>`.

    Message Output Format:
        Atlas [BOT] - 3:00 PM
        `message`
        # `title` (with `link`)
        # `attachment_text`


    :param message: Text that appears before the attachment
    :param title: Often the name of the site
    :param link: Often a link to the site
    :param attachment_text: Description of result of action
    :param level: 'Level' creates the color bar next to the fields.
     Values for level are 'good' (green), 'warning' (orange), 'danger' (red)
     or a hex value.
     :param user: The user that called the action.
    """
    # We want to notify the channel if we get a message with 'fail' in it.
    if slack_notify:
        regexp = compile(r'fail')
        if regexp.search(message) is not None:
            message_text = '<!channel> ' + environment + ' - ' + message
        else:
            message_text = environment + ' - ' + message
        fallback = title + ' - ' + link + ' - ' + attachment_text
        payload = {
            "text": message_text,
            "username": 'Atlas',
            "attachments": [
                {
                    "fallback": fallback,
                    "color": level,
                    "author_name": user,
                    "title": title,
                    "title_link": link,
                    "text": attachment_text,
                }
            ]
        }
        if environment == 'local':
            payload['channel'] ='@{0}'.format(user)

        # We need 'json=payload' vs. 'payload' because arguments can be passed in
        # any order. Using json=payload instead of data=json.dumps(payload) so that
        # we don't have to encode the dict ourselves. The Requests library will do
        # it for us.
        r = requests.post(slack_url, json=payload)
        if not r.ok:
            print r.text
