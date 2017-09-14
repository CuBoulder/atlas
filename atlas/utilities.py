"""
Utility functions.
"""
import sys
import logging
import json
import smtplib
from re import compile as re_compile
from random import choice
from string import lowercase
from hashlib import sha1
from email.mime.text import MIMEText

from cryptography.fernet import Fernet
from eve.auth import BasicAuth
from flask import g
import OpenSSL
import mysql.connector as mariadb
import requests
import ldap

from atlas.config import (ATLAS_LOCATION, ALLOWED_USERS, LDAP_SERVER, LDAP_ORG_UNIT,
                          LDAP_DNS_DOMAIN_NAME, ENCRYPTION_KEY, DATABASE_USER,
                          DATABASE_PASSWORD, ENVIRONMENT, SLACK_NOTIFICATIONS,
                          SERVICE_ACCOUNT_USERNAME, SERVICE_ACCOUNT_PASSWORD, SSL_VERIFICATION,
                          SLACK_USERNAME, SLACK_URL, SEND_NOTIFICATION_EMAILS,
                          SEND_NOTIFICATION_FROM_EMAIL, EMAIL_HOST, EMAIL_PORT, EMAIL_USERNAME,
                          EMAIL_PASSWORD)
from atlas.config_servers import (SERVERDEFS, API_URLS, LOGSTASH_URL)

# Setup a sub-logger. See tasks.py for longer comment.
log = logging.getLogger('atlas.utilities')


if ATLAS_LOCATION not in sys.path:
    sys.path.append(ATLAS_LOCATION)


class AtlasBasicAuth(BasicAuth):
    """
    Basic Authentication
    """
    def check_auth(self, username, password):
        """
        Check user supplied credentials against LDAP.
        """
        # Check if username is in 'allowed users' defined in config_local.py
        if username not in ALLOWED_USERS:
            return False
        # Initialize LDAP. The initialize() method returns an LDAPObject object, which contains
        # methods for performing LDAP operations and retrieving information about the LDAP
        # connection and transactions.
        l = ldap.initialize(LDAP_SERVER)

        # Start the connection using TLS.
        try:
            l.start_tls_s()
        except ldap.LDAPError, e:
            log.error(e.message)
            if type(e.message) == dict and e.message.has_key('desc'):
                log.error(e.message['desc'])
            else:
                log.error(e)

        ldap_distinguished_name = "uid={0},ou={1},{2}".format(
            username, LDAP_ORG_UNIT, LDAP_DNS_DOMAIN_NAME)
        log.debug(ldap_distinguished_name)

        # Add the username as a Flask application global.
        g.username = username

        try:
            # Try a synchronous bind (we want synchronous so that the command is blocked until the
            # bind gets a result. If you can bind, the credentials are valid.
            l.simple_bind_s(ldap_distinguished_name, password)
            log.debug('LDAP | %s | Bind successful', username)
            return True
        except ldap.INVALID_CREDENTIALS:
            log.debug('LDAP | %s | Invalid credentials', username)
        finally:
            try:
                log.debug('LDAP | unbind')
                l.unbind()
            except ldap.LDAPError, e:
                log.error('LDAP | unbind failed')
                pass

        # Apparently this was a bad login attempt
        log.info('LDAP | %s | Bind failed', username)
        return False


def randomstring(length=14):
    """
    :param length: Length of the string
    :return: String of random lowercase letters.
    """
    return ''.join(choice(lowercase) for i in range(length))


def mysql_password():
    """
    Hash string twice with SHA1 and return uppercase hex digest, prepended with an asterisk.

    This function is identical to the MySQL PASSWORD() function.
    """
    start = randomstring()
    pass1 = sha1(start).digest()
    pass2 = sha1(pass1).hexdigest()
    return "*" + pass2.upper()


# See https://cryptography.io/en/latest/fernet/#implementation
def encrypt_string(string):
    """
    Use Fernet symmetric encryption to encrypt a string.
    """
    cipher = Fernet(ENCRYPTION_KEY)
    msg = cipher.encrypt(string)
    encrypted = msg.encode('hex')
    return encrypted


def decrypt_string(string):
    """
    Use Fernet symmetric encryption to decrypt a string.
    """
    cipher = Fernet(ENCRYPTION_KEY)
    msg = string.decode('hex')
    decrypted = cipher.decrypt(msg)
    return decrypted


def create_database(site_sid, site_db_key):
    """
    Create a database and user for the
    :param site: site object
    """
    log.info('Create Database | %s', site_sid)
    # Start connection
    mariadb_connection = mariadb.connect(
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        host=SERVERDEFS[ENVIRONMENT]['database_servers']['master'],
        port=SERVERDEFS[ENVIRONMENT]['database_servers']['port']
    )

    cursor = mariadb_connection.cursor()

    # Create database
    try:
        cursor.execute("CREATE DATABASE `{0}`;".format(site_sid))
    except mariadb.Error as error:
        log.error('Create Database | %s | %s', site_sid, error)
        raise

    instance_database_password = decrypt_string(site_db_key)
    # Add user
    try:
        if ENVIRONMENT != 'local':
            cursor.execute("CREATE USER '{0}'@'{1}' IDENTIFIED BY '{2}';".format(
                site_sid,
                SERVERDEFS[ENVIRONMENT]['database_servers']['user_ip_range'],
                instance_database_password))
        else:
            cursor.execute("CREATE USER '{0}'@'localhost' IDENTIFIED BY '{1}';".format(
                site_sid, instance_database_password))
    except mariadb.Error as error:
        log.error('Create User | %s | %s', site_sid, error)
        raise

    # Grant privileges
    try:
        if ENVIRONMENT != 'local':
            cursor.execute("GRANT ALL PRIVILEGES ON {0}.* TO '{0}'@'{1}';".format(
                site_sid,
                SERVERDEFS[ENVIRONMENT]['database_servers']['user_ip_range']))
        else:
            cursor.execute("GRANT ALL PRIVILEGES ON {0}.* TO '{0}'@'localhost';".format(site_sid))
    except mariadb.Error as error:
        log.error('Grant Privileges | %s | %s', site_sid, error)
        raise

    mariadb_connection.commit()
    mariadb_connection.close()

    log.info('Create Database | %s | Success', site_sid)


def delete_database(site_sid):
    """
    Delete database and user

    :param site_id: SID for instance to remove.
    """
    log.info('Delete Database | %s', site_sid)
    # Start connection
    mariadb_connection = mariadb.connect(
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        host=SERVERDEFS[ENVIRONMENT]['database_servers']['master'],
        port=SERVERDEFS[ENVIRONMENT]['database_servers']['port']
    )
    cursor = mariadb_connection.cursor()

    # Drop database
    try:
        cursor.execute("DROP DATABASE IF EXISTS `{0}`;".format(site_sid))
    except mariadb.Error as error:
        log.error('Drop Database | %s | %s', site_sid, error)

    # Drop user
    try:
        cursor.execute("DROP USER '{0}'@'{1}0';".format(
            site_sid,
            SERVERDEFS[ENVIRONMENT]['database_servers']['user_ip_range']))
    except mariadb.Error as error:
        log.error('Drop User | %s | %s', site_sid, error)

    mariadb_connection.commit()
    mariadb_connection.close()
    log.info('Delete Database | %s | Success', site_sid)


def post_eve(resource, payload):
    """
    Make calls to the Atlas API.

    :param resource: A resource as defined in config_data_structure.py
    :param payload: argument string
    """
    url = "{0}/{1}".format(API_URLS[ENVIRONMENT], resource)
    headers = {"content-type": "application/json"}
    try:
        r = requests.post(url, auth=(SERVICE_ACCOUNT_USERNAME, SERVICE_ACCOUNT_PASSWORD), headers=headers, verify=SSL_VERIFICATION, data=json.dumps(payload))
    except Exception as error:
        log.error('POST to Atlas | URL - %s | Error - %s', url, error)

    return r.json()


def get_eve(resource, query=None):
    """
    Make calls to the Atlas API.

    :param resource:
    :param query: argument string
    :return: dict of items that match the query string.
    """
    if query:
        url = "{0}/{1}?{2}".format(API_URLS[ENVIRONMENT], resource, query)
    else:
        url = "{0}/{1}".format(API_URLS[ENVIRONMENT], resource)
    log.debug('utilities | Get Eve | url - %s', url)

    try:
        r = requests.get(url, auth=(SERVICE_ACCOUNT_USERNAME,
                                    SERVICE_ACCOUNT_PASSWORD), verify=SSL_VERIFICATION)
    except Exception as error:
        log.error('GET to Atlas | URL - %s | Error - %s', url, error)

    return r.json()


def get_single_eve(resource, id):
    """
    Make calls to the Atlas API.

    :param resource:
    :param id: _id string
    :return: dict of items that match the query string.
    """
    url = "{0}/{1}/{2}".format(API_URLS[ENVIRONMENT], resource, id)
    log.debug('utilities | Get Eve Single | url - %s', url)

    try:
        r = requests.get(url, auth=(SERVICE_ACCOUNT_USERNAME,
                                    SERVICE_ACCOUNT_PASSWORD), verify=SSL_VERIFICATION)
    except Exception as error:
        log.error('GET to Single item in Atlas | URL - %s | Error - %s', url, error)

    return r.json()


def patch_eve(resource, id, request_payload):
    """
    Patch items in the Atlas API.

    :param resource:
    :param id:
    :param request_payload:
    :return:
    """
    url = "{0}/{1}/{2}".format(API_URLS[ENVIRONMENT], resource, id)
    get_etag = get_single_eve(resource, id)
    headers = {'Content-Type': 'application/json', 'If-Match': get_etag['_etag']}

    try:
        r = requests.patch(url, headers=headers, data=json.dumps(request_payload), auth=(
            SERVICE_ACCOUNT_USERNAME, SERVICE_ACCOUNT_PASSWORD), verify=SSL_VERIFICATION)
    except Exception as error:
        log.error('PATCH to Atlas | URL - %s | Error - %s', url, error)

    return r.json()


def delete_eve(resource, id):
    """
    Patch items in the Atlas API.

    :param resource:
    :param id:
    :return:
    """
    url = "{0}/{1}/{2}".format(API_URLS[ENVIRONMENT], resource, id)
    get_etag = get_single_eve(resource, id)
    headers = {'Content-Type': 'application/json', 'If-Match': get_etag['_etag']}
    try:
        r = requests.delete(url, headers=headers, auth=(
            SERVICE_ACCOUNT_USERNAME, SERVICE_ACCOUNT_PASSWORD), verify=SSL_VERIFICATION)
    except Exception as error:
        log.error('DELETE to Atlas | URL - %s | Error - %s', url, error)

    return r.status_code


def get_current_code(name, code_type):
    """
    Get the current code item for a given name and type.

    :param name: string
    :param type: string
    :return: _id of the item.
    """
    query = 'where={{"meta.name":"{0}","meta.code_type":"{1}","meta.is_current":true}}'.format(
        name, code_type)
    current_code = get_eve('code', query)
    if current_code['_meta']['total'] != 0:
        return current_code['_items'][0]['_id']
    else:
        return False


def get_code(name, code_type=''):
    """
    Get the current code item for a given name and code_type.

    :param name: string
    :param code_type: string
    :return: _id of the item.
    """
    if code_type:
        query = 'where={{"meta.name":"{0}","meta.code_type":"{1}"}}'.format(name, code_type)
    else:
        query = 'where={{"meta.name":"{0}"}}'.format(name)
    code_get = get_eve('code', query)
    log.debug('Get Code | Result | %s', code_get)
    return code_get


def get_code_name_version(code_id):
    """
    Get the name and version for a code item.
    :param code_id: string '_id' for a code item
    :return: string 'label'-'version'
    """
    code = get_single_eve('code', code_id)
    code_name = code['meta']['name']
    code_version = code['meta']['version']
    return '{0}-{1}'.format(code_name, code_version)


def get_code_label(code_id):
    """
    Get the label for a code item.
    :param code_id: string '_id' for a code item
    :return: string 'label'-'version'
    """
    code = get_single_eve('code', code_id)
    return code['meta']['label']


def import_code(query):
    """
    Import code definitions from a URL. Should be a JSON file export from Atlas or a live Atlas code
    endpoint.

    :param query: URL for JSON to import
    """
    r = requests.get(query)
    log.debug('Import Code | JSON Import | %s', r.json())
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
        if code['meta'].get('label'):
            payload['meta']['label'] = code['meta']['label']
        post_eve('code', payload)


def rebalance_update_groups(item):
    """
    Redistribute instances into update groups.
    :param item: command item
    :return:
    """
    site_query = 'where={0}'.format(item['query'])
    sites = get_eve('sites', site_query)
    installed_update_group = 0
    launched_update_group = 0
    if not sites['_meta']['total'] == 0:
        for site in sites['_items']:
            # Only update if the group is less than 11.
            if site['update_group'] < 11:
                if site['status'] == 'launched':
                    patch_payload = '{{"update_group": {0}}}'.format(launched_update_group)
                    if launched_update_group < 10:
                        launched_update_group += 1
                    else:
                        launched_update_group = 0
                if site['status'] == 'installed':
                    patch_payload = '{{"update_group": {0}}}'.format(installed_update_group)
                    if installed_update_group < 2:
                        installed_update_group += 1
                    else:
                        installed_update_group = 0
                if patch_payload:
                    patch_eve('sites', site['_id'], patch_payload)


def post_to_slack_payload(payload):
    """
    Posts a message to a given channel using the Slack Incoming Webhooks API.
    See https://api.slack.com/docs/message-formatting.

    :param payload: Payload suitable for POSTing to Slack.
    """
    if SLACK_NOTIFICATIONS:
        if ENVIRONMENT == 'local':
            payload['channel'] = '@{0}'.format(SLACK_USERNAME)

        # We need 'json=payload' vs. 'payload' because arguments can be passed
        # in any order. Using json=payload instead of data=json.dumps(payload)
        # so that we don't have to encode the dict ourselves. The Requests
        # library will do it for us.
        r = requests.post(SLACK_URL, json=payload)
        if not r.ok:
            print r.text


def post_to_logstash_payload(payload):
    """
    Posts a message to our logstash instance.

    :param payload: JSON encoded payload.
    """
    if ENVIRONMENT != 'local':
        try:
            r = requests.post(LOGSTASH_URL, json=payload)
        except Exception as error:
            log.error('POST to Logstash | %s', error)



def send_email(email_message, email_subject, email_to):
    """
    Sends email

    :param email_message: content of the email to be sent.
    :param email_subject: content of the subject line
    :param email_to: list of email address(es) the email will be sent to
    """
    if SEND_NOTIFICATION_EMAILS:
        # We only send plaintext to prevent abuse.
        msg = MIMEText(email_message, 'plain')
        msg['Subject'] = email_subject
        msg['From'] = SEND_NOTIFICATION_FROM_EMAIL
        msg['To'] = ", ".join(email_to)

        s = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        s.starttls()
        s.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        s.sendmail(SEND_NOTIFICATION_FROM_EMAIL, email_to, msg.as_string())
        s.quit()
