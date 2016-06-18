import sys
import ldap
import logging
import json
import datetime

from eve import Eve
from eve.auth import BasicAuth

from atlas import tasks
from atlas.config import allowed_users, ldap_server, ldap_org_unit, ldap_dns_domain_name


path = '/data/code'
if path not in sys.path:
    sys.path.append(path)

# Callbacks
def pre_post_callback(resource, request):
    """
    Callback for POST to all endpoints.

    Allows us to hook into any create event *before* the Mongo object is created.

    :param resource: resource accessed
    :param request: original flask.request object
    """
    # We use request.json instead of request.form or request.values because
    # our data comes in as JSON.
    # See http://flask.pocoo.org/docs/0.11/api/#incoming-request-data for
    # debugging incoming requests.
    #app.logger.debug(request.json)
    # TODO: Check to see if a record with the same combination of fields exists.
    # if resource == 'code':
    #
    # elif resource == 'site':


def post_post_code_callback(resource, request, payload):
    """
    Callback for POST to `code` endpoint.

    Allows us to hook into 'code' create events *after* the Mongo object has been created.

    :param resource: resource accessed
    :param request: original flask.request object
    :param payload: response payload
    :return:
    """
    app.logger.debug(request.json)
    tasks.code_deploy.delay(request.json)

def post_post_site_callback(resource, request, payload):
    """
    Callback for POST to `code` endpoint.

    Allows us to hook into 'site' create events *after* the Mongo object has been created.

    :param resource: resource accessed
    :param request: original flask.request object
    :param payload: response payload
    :return:
    """
    app.logger.debug(request.json)
    tasks.site_provison.delay(request.json)

# TODO: Set it up to mark what user updated the record.
# auto fill _created_by and _modified_by user fields
# created_by_field = '_created_by'
# modified_by_field = '_modified_by'
# for resource in settings['DOMAIN']:
#     settings['DOMAIN'][resource]['schema'][created_by_field] = {'type': 'string'}
#     settings['DOMAIN'][resource]['schema'][modified_by_field] = {'type': 'string'}
# def pre_insert(resource, documents):
#     user = g.get('user', None)
#     if user is not None:
#         for document in documents:
#             document[created_by_field] = user
#             document[modified_by_field] = user
# def pre_replace(resource, document):
#     user = g.get('user', None)
#     if user is not None:
#         document[modified_by_field] = user


# Utilities
class AtlasBasicAuth(BasicAuth):
    """
    Basic Authentication
    """
    def check_auth(self, username, password, allowed_roles=['default'], resource='default', method='default'):
        # Check if username is in the array of allowed users defined in config_local.py
        if username not in allowed_users:
            return False
        """
        Test credentials against LDAP.

        Initialize LDAP. The initialize() method returns an LDAPObject object, which contains methods for performing LDAP operations and retrieving information about the LDAP connection and transactions.
        """
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
            """
            Try a synchronous bind (we want synchronous so that the command is blocked until the bind gets a result. If you can bind, the credentials are valid.
            """
            result = l.simple_bind_s(ldap_distinguished_name, password)
            app.logger.info('LDAP - {0} - Bind successful'.format(username))
            return True
        except ldap.INVALID_CREDENTIALS:
            app.logger.info('LDAP - {0} - Invalid credentials'.format(username))

        # Apparently this was a bad login attempt
        app.logger.info('LDAP - {0} - Bind failed'.format(username))
        return False


# TODO: Add in a message (DONE) and result broker, I don't want to use the DB. It is currently 41 GB for inventory.


"""
Setup the application and logging.
"""
# Tell Eve to use Basic Auth where our data structure is defined.
app = Eve(auth=AtlasBasicAuth, settings="/data/code/atlas/config_data_structure.py")
# TODO: Remove debug mode.
app.debug = True

# Add specific callbacks
# Pattern is: `atlas.on_{Hook}_{Method}_{Resource}`
#app.on_pre_POST += pre_post_callback
#app.on_insert += pre_insert
#app.on_replace += pre_replace
app.on_post_POST_code += post_post_code_callback
app.on_post_POST_site += post_post_site_callback


if __name__ == '__main__':
    # Enable logging to 'atlas.log' file
    # TODO: Figure out why the stuff shows in the apache error log, not this location.
    handler = logging.FileHandler('/var/log/celery/atlas.log')
    # The default log level is set to WARNING, so we have to explicitly set the
    # logging level to Debug.
    app.logger.setLevel(logging.BEDUG)
    # Append the handler to the default application logger
    app.logger.addHandler(handler)

    # This goes last.
    app.run(host='0.0.0.0', ssl_context='adhoc')
