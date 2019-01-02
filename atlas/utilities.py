"""
Utility functions.
"""
import os
import sys
import logging
import json
import subprocess
import stat
import smtplib
import re
from math import ceil
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
                          EMAIL_PASSWORD, EMAIL_USERS_EXCLUDE, SAML_AUTH, CODE_ROOT,
                          INSTANCE_CODE_IGNORE_REGEX)
from atlas.config_servers import (SERVERDEFS, API_URLS)
from atlas.data_structure import PAGINATION_DEFAULT

# Setup a sub-logger. See tasks.py for longer comment.
log = logging.getLogger('atlas.utilities')


if ATLAS_LOCATION not in sys.path:
    sys.path.append(ATLAS_LOCATION)


class AtlasBasicAuth(BasicAuth):
    """
    Basic Authentication
    """
    def check_auth(self, username, password, allowed_roles=['default'], resource='default', method='default'):
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
        cursor.execute("CREATE DATABASE IF NOT EXISTS `{0}`;".format(site_sid))
    except mariadb.Error as error:
        log.error('Create Database | %s | %s', site_sid, error)
        raise

    instance_database_password = decrypt_string(site_db_key)
    # Grant privileges/add user
    try:
        if ENVIRONMENT != 'local':
            cursor.execute("GRANT ALL PRIVILEGES ON {0}.* TO '{0}'@'{1}' IDENTIFIED BY '{2}';".format(
                site_sid,
                SERVERDEFS[ENVIRONMENT]['database_servers']['user_host_pattern'],
                instance_database_password))
        else:
            cursor.execute("GRANT ALL PRIVILEGES ON {0}.* TO '{0}'@'localhost' IDENTIFIED BY '{1}';".format(
                site_sid, instance_database_password))
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
        cursor.execute("DROP USER '{0}'@'{1}';".format(
            site_sid,
            SERVERDEFS[ENVIRONMENT]['database_servers']['user_host_pattern']))
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

    r = requests.post(url, auth=(SERVICE_ACCOUNT_USERNAME, SERVICE_ACCOUNT_PASSWORD),
                      headers=headers, verify=SSL_VERIFICATION, data=json.dumps(payload))

    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        # Wasn't a 200
        log.error('POST to Atlas | URL - %s | Error - %s', url, r.json())
        return r.json()

    return r.json()


def get_eve(resource, query=None):
    """
    Make calls to the Atlas API. This handles situations where there are many pages of results.

    :param resource:
    :param query: argument string
    :return: json result of request.
    """
    url = API_URLS[ENVIRONMENT] + '/' + resource
    if query:
        url = url + '?' + query
        query_url = url
        inital_url = url + '&max_results=1'
    else:
        inital_url = url + '?max_results=1'
        query_url = None
    log.debug('utilities | Get Eve | url - %s', url)

    try:
        # Get json output
        r_inital = requests.get(
            url,
            auth=(SERVICE_ACCOUNT_USERNAME, SERVICE_ACCOUNT_PASSWORD),
            verify=SSL_VERIFICATION).json()
    except Exception as error:
        log.error('GET to Atlas | URL - %s | Error - %s', url, error)

    total_items = r_inital['_meta']['total']
    json_result = None

    if total_items > PAGINATION_DEFAULT:
        # Return the ceiling of x as a float, the smallest integer value greater than or equal to x.
        num_pages = int(ceil(total_items/PAGINATION_DEFAULT))
        # Range - Generate numbers from the first number up to, but not including the second.
        for page in range(1, num_pages + 1):
            if query_url:
                page_url = query_url + '&page={0}&max_results={1}'.format(page, PAGINATION_DEFAULT)
            else:
                page_url = url + '?page={0}&max_results={1}'.format(page, PAGINATION_DEFAULT)
            r_page = requests.get(
                page_url,
                auth=(SERVICE_ACCOUNT_USERNAME, SERVICE_ACCOUNT_PASSWORD),
                verify=SSL_VERIFICATION).json()
            log.debug('utilities | Get eve | page request - %s', r_page)
            # Merge lists
            if json_result:
                log.debug('Backup data | Original data - %s', json_result)
                log.debug('Backup data | New data - %s', r_page)
                json_result = json_result + r_page
                log.debug('Backup data | Final data - %s', json_result)
            else:
                json_result = r_page
    else:
        if query_url:
            total_url = query_url + '&max_results={0}'.format(total_items)
        else:
            total_url = url + '?max_results={0}'.format(total_items)
        json_result = requests.get(total_url, auth=(
            SERVICE_ACCOUNT_USERNAME,  SERVICE_ACCOUNT_PASSWORD), verify=SSL_VERIFICATION).json()

    return json_result


def get_single_eve(resource, id, version=None, env=ENVIRONMENT):
    """
    Make calls to the Atlas API.

    :param resource:
    :param id: _id string
    :return: dict of items that match the query string.
    """
    if version:
        url = "{0}/{1}/{2}?version={3}".format(API_URLS[env], resource, id, version)
    else:
        url = "{0}/{1}/{2}".format(API_URLS[env], resource, id)
    log.debug('utilities | Get Eve Single | url - %s', url)

    r = requests.get(url, auth=(SERVICE_ACCOUNT_USERNAME,
                                SERVICE_ACCOUNT_PASSWORD), verify=SSL_VERIFICATION)

    return r.json()

def patch_eve(resource, id, request_payload, env=ENVIRONMENT):
    """
    Patch items in the Atlas API.

    :param resource:
    :param id:
    :param request_payload:
    :return:
    """
    url = "{0}/{1}/{2}".format(API_URLS[env], resource, id)
    get_etag = get_single_eve(resource, id, env=env)
    headers = {'Content-Type': 'application/json', 'If-Match': get_etag['_etag']}

    try:
        r = requests.patch(url, headers=headers, data=json.dumps(request_payload), auth=(
            SERVICE_ACCOUNT_USERNAME, SERVICE_ACCOUNT_PASSWORD), verify=SSL_VERIFICATION)
        log.info('PATCH to Atlas | URL - %s | Response - %s', url, r.text)
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


# Code related utility functions
def code_path(item):
    """
    Determine the path for a code item
    """
    log.debug('Utilities | Code Path | Item - %s', item)
    code_dir = '{0}/{1}/{2}/{2}-{3}'.format(
        CODE_ROOT,
        code_type_directory_name(item['meta']['code_type']),
        item['meta']['name'],
        item['meta']['version']
    )
    return code_dir


def code_type_directory_name(code_type):
    """
    Determine the path for a code item
    """
    if code_type == 'library':
        return 'libraries'
    elif code_type == 'static':
        return 'static'

    return code_type + 's'


def ignore_code_file(file_to_check):
    """Check if the file matches one of the INSTANCE_CODE_IGNORE_REGEX regexes

    Arguments:
        file_to_check {string} -- filename to check

    Returns:
        bool -- TRUE if file should be ignored
    """
    # Join all regex expressions into a single expression with the pipe seperator.
    # We use '?:' since we don't care which expression matches.
    regex = '(?:%s)' % '|'.join(INSTANCE_CODE_IGNORE_REGEX)
    log.debug('Utilities | Ignore code file | regex - %s', regex)
    # Multiline modifier: ^ and $ to match the begin/end of each line (not only begin/end of string)
    search = re.search(regex, file_to_check, re.MULTILINE)
    if not search:
        log.debug('Utilities | Ignore code file | File - %s | result - %s', file_to_check, search)
    return bool(search)


def get_code(name, code_type=''):
    """
    Get the code item(s) for a given name and code_type.

    :param name: string
    :param code_type: string
    :return: response object
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
    Get the label for a code item if it has one, otherwise use the machine name and version.

    :param code_id: string '_id' for a code item
    :return: string 'label or 'name-version'
    """
    code = get_single_eve('code', code_id)
    if code['meta'].get('meta'):
        return code['meta']['label']
    else:
        return get_code_name_version(code_id)


def post_to_slack_payload(payload):
    """
    Posts a message to a given channel using the Slack Incoming Webhooks API.
    See https://api.slack.com/docs/message-formatting.

    :param payload: Payload suitable for POSTing to Slack.
    """
    if SLACK_NOTIFICATIONS:
        if ENVIRONMENT == 'local':
            payload['channel'] = '@{0}'.format(SLACK_USERNAME)
        if 'username' not in payload:
            payload['username'] = 'Atlas'
        # Using json=payload instead of data=json.dumps(payload) so that we don't have to encode the
        # dict ourselves. The Requests library will do it for us.
        r = requests.post(SLACK_URL, json=payload)
        if not r.ok:
            print r.text


def send_email(email_message, email_subject, email_to):
    """
    Sends email

    :param email_message: content of the email to be sent.
    :param email_subject: content of the subject line
    :param email_to: list of email address(es) the email will be sent to
    """
    log.debug('Send email | Message - %s | Subject - %s | To - %s',
              email_message, email_subject, email_to)
    if SEND_NOTIFICATION_EMAILS:
        # We only send plaintext to prevent abuse.
        msg = MIMEText(email_message, 'plain')
        msg['Subject'] = email_subject
        msg['From'] = SEND_NOTIFICATION_FROM_EMAIL
        final_email_to = [x for x in email_to if x not in EMAIL_USERS_EXCLUDE]
        log.info('Send email | Final To - %s', final_email_to)
        msg['To'] = ", ".join(final_email_to)

        if final_email_to:
            s = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
            s.starttls()
            s.login(EMAIL_USERNAME, EMAIL_PASSWORD)
            s.sendmail(SEND_NOTIFICATION_FROM_EMAIL, final_email_to, msg.as_string())
            s.quit()


def package_import(site, env=ENVIRONMENT, metadata=False):
    """
    Take a site record, lookup the packages, and return a list of packages to add to the instance.
    :param site: Instance to lookup
    :param env: Environment to look in
    :param metadata_list: If true return a list of metadata instead of _ids
    :return: List of package IDs or a list of hashes
    """
    if 'package' in site['code']:
        # Start with an empty list
        package_list = []
        metadata_list = []
        for package in site['code']['package']:
            package_result = get_single_eve('code', package, env=env)
            log.debug(
                'Utilities | Package import | Checking for packages | Request result - %s', package_result)
            if package_result['_deleted']:
                current_package = get_current_code(
                    package_result['meta']['name'], package_result['meta']['code_type'])
                log.debug(
                    'Utilities | Package import | Getting current version of package - %s', current_package)
                if current_package:
                    package_list.append(current_package)
                else:
                    raise Exception('There is no current version of {0}. This backup cannot be restored.'.format(
                        package_result['meta']['name']))
            else:
                package_list.append(package_result['_id'])
            # Add a tuple for the metadata_list
            metadata_list.append(
                (package_result['meta']['name'], package_result['meta']['code_type']))
    else:
        package_list = None

    if metadata:
        log.debug('Utilities | Package import | Return metadata list')
        return metadata_list

    return package_list


def package_import_cross_env(site, env=ENVIRONMENT):
    """
    Take a site record from another environment, lookup the packages, and return a list of
    equivelvant packages to add to the new instance.
    :return: List of package IDs
    """
    if 'package' in site['code']:
        metadata_list = package_import(site, env=env, metadata=True)
        package_list = []
        for item in metadata_list:
            current_package = get_current_code(item[0], item[1])
            if current_package:
                package_list.append(current_package)
            else:
                raise Exception(
                    'There is no current version of {0}. This backup cannot be restored.'.format(item[0]))
    else:
        package_list = None
    return package_list


def create_saml_database():
    """
    Create a database and user for SAML auth
    """
    log.info('Create SAML Database')
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
        cursor.execute("CREATE DATABASE `saml`;")
    except mariadb.Error as error:
        log.error('Create Database | saml | %s', error)
        raise

    instance_database_password = SAML_AUTH
    # Add user
    try:
        if ENVIRONMENT != 'local':
            cursor.execute("CREATE USER 'saml'@'{0}' IDENTIFIED BY '{1}';".format(
                SERVERDEFS[ENVIRONMENT]['database_servers']['user_host_pattern'],
                instance_database_password))
        else:
            cursor.execute("CREATE USER 'saml'@'localhost' IDENTIFIED BY '{0}';".format(
                instance_database_password))
    except mariadb.Error as error:
        log.error('Create User | saml | %s', error)
        raise

    # Grant privileges
    try:
        if ENVIRONMENT != 'local':
            cursor.execute("GRANT ALL PRIVILEGES ON saml.* TO 'saml'@'{0}';".format(
                SERVERDEFS[ENVIRONMENT]['database_servers']['user_host_pattern']))
        else:
            cursor.execute("GRANT ALL PRIVILEGES ON saml.* TO 'saml'@'localhost';")
    except mariadb.Error as error:
        log.error('Grant Privileges | saml | %s', error)
        raise

    mariadb_connection.commit()
    mariadb_connection.close()

    log.info('Create Database | saml | Success')


def delete_saml_database():
    """
    Delete database and user

    :param site_id: SID for instance to remove.
    """
    log.info('Delete Database | saml')
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
        cursor.execute("DROP DATABASE IF EXISTS `saml`;")
    except mariadb.Error as error:
        log.error('Drop Database | saml | %s', error)

    # Drop user
    try:
        if ENVIRONMENT != 'local':
            cursor.execute("DROP USER 'saml'@'{0}';".format(
                SERVERDEFS[ENVIRONMENT]['database_servers']['user_host_pattern']))
        else:
            cursor.execute("DROP USER 'saml'@'localhost';")
    except mariadb.Error as error:
        log.error('Drop User | saml | %s', error)

    mariadb_connection.commit()
    mariadb_connection.close()
    log.info('Delete Database | saml | Success')


def relative_symlink(source, destination):
    os.symlink(os.path.relpath(source, os.path.dirname(destination)), destination)


def sync(source, hosts, target, exclude=None):
    """Sync files, symlinks, and directories between servers

    Arguments:
        source {string} -- source path
        hosts {list} -- list of hosts to sync to, will be deduped by function
        target {string} -- destination path
        exclude {string} -- directory to exclude from rsync
    """

    log.info('Utilities | Sync | Source - %s', source)
    # Use `set` to dedupe the host list, and cast it back into a list
    hosts = list(set(hosts))
    # Recreate readme
    filename = source + "/README.md"
    # Remove the existing file.
    if os.access(filename, os.F_OK):
        os.remove(filename)
    f = open(filename, "w+")
    f.write("Directory is synced from Atlas. Any changes will be overwritten.")
    f.close()
    for host in hosts:
        # -a archive mode; equals -rlptgoD
        # -z compress file data during the transfer
        # trailing slash on src copies the contents, not the parent dir itself.
        # --delete delete extraneous files from dest dirs
        if exclude:
            cmd = 'rsync -aqz --exclude={0} {1}/ {2}:{3} --delete'.format(exclude, source, host, target)
        else:
            cmd = 'rsync -aqz {0}/ {1}:{2} --delete'.format(source, host, target)
        log.debug('Utilities | Sync | Command - %s | Host - %s', cmd, host)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            log.error('Utilities | Sync | Failed | Return code - %s | StdErr - %s | Host - %s', e.returncode, e.output, host)
        else:
            log.info('Utilities | Sync | Success | Host - %s', host)


def file_accessable_and_writable(file):
    """Verify that a file exists and make it writable if it is not

    Arguments:
        file {string} -- Path of file to check
    """
    if os.access(file, os.F_OK):
        # Check if file is writable
        if not os.access(file, os.W_OK):
            # Make it writable, get the current permissions and OR them together with the write bit.
            st = os.stat(file)
            os.chmod(file, st.st_mode | stat.S_IWRITE)
            return True
        return True
