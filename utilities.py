"""
Utility functions.
"""
import sys
import requests
import json
import smtplib
from random import choice
from re import compile as re_compile
from email.mime.text import MIMEText
from hashlib import sha1
from string import lowercase

import ldap
from datetime import datetime

from cryptography.fernet import Fernet
from eve.auth import BasicAuth
from flask import current_app, g
from atlas.config import *

atlas_path = '/data/code'
if atlas_path not in sys.path:
    sys.path.append(atlas_path)


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

        # Add the username as a Flask application global.
        g.username = username

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


def post_eve(resource, payload):
    """
    Make calls to the Atlas API.

    :param resource: A resource as defined in config_data_structure.py
    :param payload: argument string
    """
    url = "{0}/{1}".format(api_urls[environment], resource)
    headers = {"content-type": "application/json"}
    r = requests.post(url, auth=(service_account_username, service_account_password), headers=headers, verify=ssl_verification, data=json.dumps(payload))
    if r.ok:
        return r.json()
    else:
        return r.text


def get_eve(resource, query=None):
    """
    Make calls to the Atlas API.

    :param resource:
    :param query: argument string
    :return: dict of items that match the query string.
    """
    if query:
        url = "{0}/{1}?{2}".format(api_urls[environment], resource, query)
    else:
        url = "{0}/{1}".format(api_urls[environment], resource)
    print(url)
    r = requests.get(url, auth=(service_account_username, service_account_password), verify=ssl_verification)
    if r.ok:
        return r.json()
    else:
        return r.text


def get_single_eve(resource, id):
    """
    Make calls to the Atlas API.

    :param resource:
    :param id: _id string
    :return: dict of items that match the query string.
    """
    url = "{0}/{1}/{2}".format(api_urls[environment], resource, id)
    print(url)
    r = requests.get(url, auth=(service_account_username, service_account_password), verify=ssl_verification)
    if r.ok:
        return r.json()
    else:
        return r.text


def patch_eve(resource, id, request_payload):
    """
    Patch items in the Atlas API.

    :param resource:
    :param id:
    :param request_payload:
    :return:
    """
    url = "{0}/{1}/{2}".format(api_urls[environment], resource, id)
    get_etag = get_single_eve(resource, id)
    headers = {'Content-Type': 'application/json', 'If-Match': get_etag['_etag']}
    r = requests.patch(url, headers=headers, data=json.dumps(request_payload), auth=(service_account_username, service_account_password), verify=ssl_verification)
    if r.ok:
        return r.json()
    else:
        return r.text


def delete_eve(resource, id):
    """
    Patch items in the Atlas API.

    :param resource:
    :param id:
    :return:
    """
    url = "{0}/{1}/{2}".format(api_urls[environment], resource, id)
    get_etag = get_single_eve(resource, id)
    headers = {'Content-Type': 'application/json', 'If-Match': get_etag['_etag']}
    r = requests.delete(url, headers=headers, auth=(service_account_username, service_account_password), verify=ssl_verification)
    if r.ok:
        return r.status_code
    else:
        return r.text


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


def get_code_name_version(code_id):
    """
    Get the label and version for a code item.
    :param code_id: string '_id' for a code item
    :return: string 'label'-'version'
    """
    code = get_single_eve('code', code_id)
    code_name = code['meta']['name']
    code_version = code['meta']['version']
    return '{0}-{1}'.format(code_name, code_version)


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
        if code['meta'].get('label'):
            payload['meta']['label'] = code['meta']['label']
        post_eve('code', payload)


def rebalance_update_groups(item):
    """
    Redistribute instances into update groups.
    :param item: command item
    :return:
    """
    instance_query = 'where={0}'.format(item['query'])
    instances = get_eve('instance', instance_query)
    installed_update_group = 0
    launched_update_group = 0
    if not instances['_meta']['total'] == 0:
        for instance in instances['_items']:
            # Only update if the group is less than 11.
            if instance['update_group'] < 11:
                if instance['status'] == 'launched':
                    patch_payload = '{{"update_group": {0}}}'.format(launched_update_group)
                    if launched_update_group < 10:
                        launched_update_group += 1
                    else:
                        launched_update_group = 0
                if instance['status'] == 'installed':
                    patch_payload = '{{"update_group": {0}}}'.format(installed_update_group)
                    if installed_update_group < 2:
                        installed_update_group += 1
                    else:
                        installed_update_group = 0
                if patch_payload:
                    patch_eve('instances', instance['_id'], patch_payload)


# Deprecated use 'post_to_slack_payload'
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
        regexp = re_compile(r'fail')
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
            payload['channel'] = '@{0}'.format(slack_username)
        elif 'cron' in attachment_text:
            payload['channel'] = 'cron'

        # We need 'json=payload' vs. 'payload' because arguments can be passed
        # in any order. Using json=payload instead of data=json.dumps(payload)
        # so that we don't have to encode the dict ourselves. The Requests
        # library will do it for us.
        r = requests.post(slack_url, json=payload)
        if not r.ok:
            print r.text

def post_to_slack_payload(payload):
    """
    Posts a message to a given channel using the Slack Incoming Webhooks API. 
    See https://api.slack.com/docs/message-formatting.

    :param payload: Payload suitable for POSTing to Slack.
    """
    if slack_notify:
        if environment == 'local':
            payload['channel'] = '@{0}'.format(slack_username)

        # We need 'json=payload' vs. 'payload' because arguments can be passed
        # in any order. Using json=payload instead of data=json.dumps(payload)
        # so that we don't have to encode the dict ourselves. The Requests
        # library will do it for us.
        r = requests.post(slack_url, json=payload)
        if not r.ok:
            print r.text


def post_to_logstash_payload(payload):
    """
    Posts a message to our logstash instance.

    :param payload: JSON encoded payload.
    """
    if environment != 'local':
        r = requests.post(logstash_url, json=payload)
        if not r.ok:
            print r.text



def send_email(message, subject, to):
    """
    Sends email
    :param message: content of the email to be sent.
    :param subject: content of the subject line
    :param to: list of email address(es) the email will be sent to
    """
    if send_notification_emails:
        # We only send plaintext to prevent abuse.
        msg = MIMEText(message, 'plain')
        msg['Subject'] = subject
        msg['From'] = send_notification_from_email
        msg['To'] = ", ".join(to)

        s = smtplib.SMTP(email_host, email_port)
        s.starttls()
        s.login(email_username, email_password)
        s.sendmail(send_notification_from_email, to, msg.as_string())
        s.quit()


def migrate_to_routes():
    """
    Migrate from instance['path'] to instance['route']
    """
    # TODO Make sure p1 and other perm paths are handled.

    # Get all poolb instances that are launched 'p1'
    instance_query = '?where={"pool":"poolb-express","status":"launched","type":"express"}'
    instances = get_eve('instance', instance_query)
    log.debug('Migrate Routes | Query | Instances | %s', instances['_meta']['total'])
    log.debug('Migrate Routes | Query | Instances | %s', instances)
    # Get all homepage f5 only paths (not all indicated that they are supposed to be)
    homepage_paths_query = '?where={"pool":"poolb-homepage","status":"launched","type":{"$ne":"express"}}'
    homepage_routes = get_eve('instance', homepage_paths_query)
    log.debug('Migrate Routes | Query | Homepage Routes | %s', homepage_routes['_meta']['total'])
    log.debug('Migrate Routes | Query | Homepage Routes | %s', homepage_routes)
    # Homepage itself
    homepage_query = '?where={"pool":"poolb-homepage","status":"launched","type":"express"}'
    homepage_instance = get_eve('instance', homepage_query)
    log.debug('Migrate Routes | Query | Homepage Instance | %s',
              homepage_instance['_meta']['total'])
    log.debug('Migrate Routes | Query | Homepage Instance | %s', homepage_instance)
    # Get all legacy paths
    legacy_paths_query = '?where={"pool":"WWWLegacy","status":"launched"}'
    legacy_routes = get_eve('instance', legacy_paths_query)
    log.debug('Migrate Routes | Query | Legacy Routes | %s', legacy_routes['_meta']['total'])
    log.debug('Migrate Routes | Query | Legacy Routes | %s', legacy_routes)

    # Put the dicts of items that require a route into a list
    routes_list = []
    if not instances['_meta']['total'] == 0:
        routes_list.append(instances['_items'])
    if not homepage_routes['_meta']['total'] == 0:
        routes_list.append(homepage_routes['_items'])
    if not homepage_instance['_meta']['total'] == 0:
        routes_list.append(homepage_instance['_items'])
    if not legacy_routes['_meta']['total'] == 0:
        routes_list.append(legacy_routes['_items'])

    if routes_list:
        for route_dict in routes_list:
            create_routes(route_dict)


def create_routes(instances):
    """
    Create routes and associate them with their instances.abs

    :param instances: dict of instances that need routes
    """
    for instance in instances:
        log.debug('Create Route | Instance | %s', instance)
        # Convert the pool field into what we need for type
        route_type = instance['pool']
        route_type = route_type.lower()
        if route_type == 'WWWLegacy':
            route_type = 'legacy'

        if instance['dates']['launched']:
            date_created = instance['dates']['launched']
        else:
            date_created = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")

        # Setup payload
        payload = {
            'route_type': route_type,
            'source': instance['path'],
            'dates': {
                'created': date_created
            },
            'created_by':'migration',
        }

        if instance['pool'] == 'poolb-express' or (instance['pool'] == 'poolb-homepage' and instance['type'] == 'express'):
            log.debug('Create Route | Instance ID Found')
            payload['instance'] = instance['_id']

        log.debug('Create Route | POST Route Payload | %s', payload)
        create_route_request = post_eve('route', payload)
        log.debug('Create Route | POST Response | %s | %s', instance, create_route_request)
        if create_route_request:
            instance_patch = {
                'route': create_route_request['item']['_id']
            }
            log.debug('Create Route | PATCH Instance Payload | %s', instance_patch)
            patch_instance_request = patch_eve('instance', instance['_id'], instance_patch)
            log.debug('Create Route | PATCH Instance Response | %s | %s', instance, patch_instance_request)
