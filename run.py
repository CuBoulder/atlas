"""
    atlas.run.py
    ~~~~~~~~~~~
    The API launch script.
"""
import os
import sys
import logging
from logging.handlers import WatchedFileHandler
import ssl

from eve import Eve
from flask import jsonify, make_response
from atlas import callbacks
from atlas import utilities
from atlas.tasks import saml_create, saml_delete
from atlas.config import (ATLAS_LOCATION, VERSION_NUMBER, SSL_KEY_FILE, SSL_CRT_FILE, LOG_LOCATION,
                          ENVIRONMENT)


if ATLAS_LOCATION not in sys.path:
    sys.path.append(ATLAS_LOCATION)


# Load the settings file using a robust path so it works when
# the script is imported from the test suite.
THIS_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
SETTINGS_FILE = os.path.join(THIS_DIRECTORY, 'atlas/data_structure.py')

# Name our app (using 'import_name') so that we can easily create sub loggers.
# Use our HTTP Basic Auth class which checks against LDAP.
# Import the data structures and Eve settings.
app = Eve(import_name='atlas', auth=utilities.AtlasBasicAuth, settings=SETTINGS_FILE)

# Enable logging to 'atlas.log' file.
LOG_HANDLER = WatchedFileHandler(LOG_LOCATION)
LOG_HANDLER.setFormatter(logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s'))

# The default log level is set to WARNING, so we have to explicitly set the logging level to Info.
app.logger.setLevel(logging.INFO)
if ENVIRONMENT == 'local':
    app.logger.setLevel(logging.DEBUG)
# Append the handler to the default application logger
app.logger.addHandler(LOG_HANDLER)

# Specific callbacks.
# Use pre event hooks if there is a chance you want to abort.
# Use DB hooks if you want to modify data on the way in.

# Request event hooks.
app.on_pre_POST += callbacks.pre_post_callback
app.on_pre_POST_sites += callbacks.pre_post_sites_callback
app.on_pre_DELETE_code += callbacks.pre_delete_code_callback
app.on_pre_DELETE_sites += callbacks.pre_delete_sites_callback
# Database event hooks.
app.on_insert_code += callbacks.on_insert_code_callback
app.on_insert_sites += callbacks.on_insert_sites_callback
app.on_inserted_sites += callbacks.on_inserted_sites_callback
app.on_update_code += callbacks.on_update_code_callback
app.on_update_sites += callbacks.on_update_sites_callback
app.on_update_commands += callbacks.on_update_commands_callback
app.on_updated_code += callbacks.on_updated_code_callback
app.on_delete_item_code += callbacks.on_delete_item_code_callback
app.on_insert += callbacks.pre_insert
app.on_update += callbacks.pre_update
app.on_replace += callbacks.pre_replace


@app.errorhandler(409)
def custom409(error):
    response = jsonify({'message': error.description})
    response.status_code = 409
    return response


@app.route('/version')
def version():
    response = make_response(VERSION_NUMBER)
    return response

@app.route('/saml/create', methods=['GET', 'POST'])
@requires_auth('sites')
def saml_create():
    if flask.request.method == 'POST':
        response = make_response("Started SAML database creation")
        saml_create.delay()
    else:
        response = make_response("Did you mean to POST?")
    return response


@app.route('/saml/delete', methods=['GET', 'POST'])
@requires_auth('sites')
def saml_delete():
    if flask.request.method == 'POST':
        response = make_response("Started SAML database delete")
        saml_delete.delay()
    else:
        response = make_response("Did you mean to POST?")
    return response


# This config is only used when running via python, rather than mod_wsgi
if __name__ == '__main__':
    ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ctx.load_cert_chain(SSL_CRT_FILE, SSL_KEY_FILE)

    # This goes last.
    app.run(host='0.0.0.0', ssl_context=ctx)
