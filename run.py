"""
    atlas.run.py
    ~~~~~~~~~~~
    The API launch script.
"""
import os
import sys
import json
import logging
from logging.handlers import WatchedFileHandler
import ssl

from collections import Counter
from eve import Eve
from eve.auth import requires_auth
from flask import jsonify, make_response, abort, request

from atlas import callbacks
from atlas import tasks
from atlas import utilities
from atlas.config import (ATLAS_LOCATION, VERSION_NUMBER, SSL_KEY_FILE, SSL_CRT_FILE, LOG_LOCATION,
                          ENVIRONMENT, API_URLS)


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
# TODO: Remove debug mode.
app.debug = True

# Enable logging to 'atlas.log' file.
LOG_HANDLER = WatchedFileHandler(LOG_LOCATION)
LOG_HANDLER.setFormatter(logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s'))

# The default log level is set to WARNING, so we have to explicitly set the logging level to Info.
app.logger.setLevel(logging.INFO)
if ENVIRONMENT == 'local':
    app.logger.setLevel(logging.DEBUG)
# Append the handler to the default application logger
app.logger.addHandler(LOG_HANDLER)

# Hook into the request flow early
@app.route('/backup/import', methods=['POST'])
@requires_auth('backup')
def import_backup():
    """
    Import a backup to a new instance.
    """
    backup_request = request.get_json()
    app.logger.debug('Backup | Import | %s', backup_request)
    # Get the backup and then the site records.
    if not (backup_request['env'] and backup_request['id']):
        abort(409, 'Error: Missing env (local, dev, test, prod) and id.')
    elif not backup_request['env']:
        abort(409, 'Error: Missing env (local, dev, test, prod).')
    elif not backup_request['id']:
        abort(409, 'Error: Missing id.')
    elif backup_request['env'] not in ['local', 'dev', 'test', 'prod']:
        abort(409, 'Error: Not a valid env choose from [local, dev, test, prod].')
    backup_record = utilities.get_single_eve(
        'backup', backup_request['id'], env=backup_request['env'])
    app.logger.debug('Backup | Import | Backup record - %s', backup_record)
    # TODO: What if 404s
    site_record = utilities.get_single_eve(
        'sites', backup_record['site'], backup_record['site_version'], env=backup_request['env'])
    app.logger.debug('Backup | Import | Site record - %s', site_record)
    # TODO: What if 404s

    try:
        package_list = utilities.package_import(site_record, env=backup_request['env'])
    except Exception as error:
        abort(409, error)


@app.route('/backup/<string:backup_id>/restore', methods=['POST'])
# TODO: Test what happens with 404 for backup_id
@requires_auth('backup')
def restore_backup(backup_id):
    """
    Restore a backup to a new instance.
    :param machine_name: id of backup to restore
    """
    app.logger.debug('Backup | Restore | %s', backup_id)
    backup_record = utilities.get_single_eve('backup', backup_id)
    original_instance = utilities.get_single_eve('sites', backup_record['site'], backup_record['site_version'])
    # If packages are still active, add them; if not, find a current version
    # and add it; if none, error
    try:
        package_list = utilities.package_import(original_instance)
    except Exception as error:
        abort(409, error)

    tasks.backup_restore.delay(backup_record, original_instance, package_list)
    response = make_response('Restore started')
    return response


@app.route('/sites/<string:site_id>/backup', methods=['POST'])
# TODO: Test what happens with 404 for site_id
@requires_auth('backup')
def create_backup(site_id):
    """
    Create a backup of an instance.
    :param machine_name: id of instance to restore
    """
    app.logger.debug('Backup | Create | Site ID - %s', site_id)
    site = utilities.get_single_eve('sites', site_id)
    app.logger.debug('Backup | Create | Site Response - %s', site)
    tasks.backup_create.delay(site=site, backup_type='on_demand')
    response = make_response('Backup started')
    return response


@app.route('/sites/aggregation', methods=['GET'])
@app.route('/sites/agg', methods=['GET'])
@requires_auth('sites')
def sites_statistics():
    """
    Give some basic aggregations about site objects
    """
    app.logger.debug('Sites | Aggregations')
    express_result = utilities.get_eve('sites','where={"type":"express","f5only":false}&max_results=2000')
    legacy_result = utilities.get_eve('sites','where={"type":"legacy","f5only":false}&max_results=2000')
    app.logger.debug('Sites | Aggregations | Express Result - %s', express_result)
    app.logger.debug('Sites | Aggregations | Legacy Result - %s', legacy_result)
    # Express sites
    express_sites = express_result['_items']
    agg = {}
    count = Counter()
    bundle = Counter()
    bundle_total = 0
    ## Total by state
    for site in express_sites:
        count[site['status']] += 1
        if site['code'].get('pacakge'):
            bundle_total += 1
    agg['express'] = {'status': dict(count)}
    # Total
    agg['express']['status']['total'] = express_result['_meta']['total']
    ## Total with bundles
    agg['express']['bundles'] = {'total': bundle_total}
    # Legacy
    ## Total routes
    agg['legacy'] = {'total': legacy_result['_meta']['total']}

    response = make_response(jsonify(agg))
    return response


@app.route('/sites/<string:site_id>/heal_packages', methods=['POST'])
# TODO: Test what happens with 404 for site_id
@requires_auth('sites')
def heal_instance(site_id):
    """
    Create a backup of an instance.
    :param machine_name: id of instance to restore
    """
    app.logger.debug('Site | Heal | Site ID - %s', site_id)
    instance = utilities.get_single_eve('sites', site_id)
    tasks.heal_instance.delay(instance)
    return make_response('Instance heal has been initiated.')


@app.route('/commands/heal_instance_packages', methods=['POST'])
def get_command():
    """
    Get a single command.
    :param machine_name: command to return a definition for.
    """
    # Loop through the commands list and grab the one we want
    app.logger.debug('Command | Execute | Heal instances')
    instance_query = 'where={"type":"express","f5only":false}&max_results=2000'
    instances = utilities.get_eve('sites', instance_query)
    for instance in instances['_items']:
        tasks.heal_instance.delay(instance)
        continue
    return make_response('Command "Heal Instances" has been initiated.')


# Specific callbacks.
# Use pre event hooks if there is a chance you want to abort.
# Use DB hooks if you want to modify data on the way in.

# Request event hooks.
app.on_pre_POST += callbacks.pre_post
app.on_pre_POST_sites += callbacks.pre_post_sites
app.on_pre_DELETE_code += callbacks.pre_delete_code
app.on_pre_DELETE_sites += callbacks.pre_delete_sites
# Database event hooks.
app.on_insert_code += callbacks.on_insert_code
app.on_insert_sites += callbacks.on_insert_sites
app.on_inserted_sites += callbacks.on_inserted_sites
app.on_update_code += callbacks.on_update_code
app.on_update_sites += callbacks.on_update_sites
app.on_update_commands += callbacks.on_update_commands
app.on_updated_code += callbacks.on_updated_code
app.on_delete_item_code += callbacks.on_delete_item_code
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


# This config is only used when running via python, rather than mod_wsgi
if __name__ == '__main__':
    ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ctx.load_cert_chain(SSL_CRT_FILE, SSL_KEY_FILE)

    # This goes last.
    app.run(host='0.0.0.0', ssl_context=ctx)
