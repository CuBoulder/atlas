import sys
import logging
import random
import json

from eve import Eve
from hashlib import sha1
from atlas import tasks
from atlas import utilities
from atlas.config import *


path = '/data/code'
if path not in sys.path:
    sys.path.append(path)

# TODO: PATCH for code for commit_hash, version, or is_current
# TODO: DELETE for code
# TODO: Validate that each code type is correct for a site. IE no core as a profile.
# TODO: PATCH for site
# TODO: DELETE for site
# TODO: POST for command
# TODO: GET for command
# TODO: DELETE for a command.
# TODO: Make Atlas autodiscover resources
# TODO: Create requirements.txt


# Callbacks
def pre_post_callback(resource, request):
    """
    Pre callback for POST to all endpoints.

    :param resource: resource accessed
    :param request: flask.request object
    """
    app.logger.debug('POST to {0} resource\nRequest:\n{1}'.format(resource, request.json))


def pre_post_code_callback(request):
    """
    Pre callback for POST to 'code' endpoint.

    Set 'meta.is_current' for code items with the same meta data to False.

    :param request: flask.request object
    """
    if request.json['meta']['is_current']:
        # Need a lowercase string when querying boolean values. Python
        # stores it as 'True'.
        query = 'where={{"meta.name":"{0}","meta.code_type":"{1}","meta.is_current": {2}}}'.format(request.json['meta']['name'], request.json['meta']['code_type'], str(request.json['meta']['is_current']).lower())
        code_get = utilities.get_eve('code', query)
        app.logger.debug(code_get)
        for code in code_get['_items']:
            request_payload = {'meta.is_current': False}
            utilities.patch_eve('code', code['_id'], code['_etag'], request_payload)


def pre_patch_code_callback(request):
    """
    Pre callback for PATCH to 'code' endpoint.

    Set 'meta.is_current' for code items with the same meta data to False.

    :param request: flask.request object
    """
    if request.json['meta']['is_current']:
        # Need a lowercase string when querying boolean values. Python
        # stores it as 'True'.
        query = 'where={{"meta.name":"{0}","meta.code_type":"{1}","meta.is_current": {2}}}'.format(request.json['meta']['name'], request.json['meta']['code_type'], str(request.json['meta']['is_current']).lower())
        code_get = utilities.get_eve('code', query)
        app.logger.debug(code_get)
        for code in code_get['_items']:
            request_payload = {'meta.is_current': False}
            utilities.patch_eve('code', code['_id'], code['_etag'], request_payload)


def post_post_callback(resource, request, payload):
    """
    Post callback for POST to all endpoints.

    :param resource: resource accessed
    :param request: original flask.request object
    :param payload: the response payload from Eve
    """
    app.logger.debug('POST to {0} resource\nPayload:\n{1}'.format(resource, payload.__dict__))


def post_post_code_callback(request, payload):
    """
    Post callback for POST to `code` endpoint.

    Get code onto servers after the document is created.

    :param request: original flask.request object
    :param payload: response payload
    """
    # Verify that the POST was successful before we do anything else.
    # Status code '201 Created'.
    if payload._status_code == 201:
        deploy_result = tasks.code_deploy.delay(request.json)


def post_patch_code_callback(request, payload):
    """
    Post callback for POST to `code` endpoint.

    Get code onto servers after the document is created.

    :param request: original flask.request object
    :param payload: response payload
    """
    # Verify that the PATCH was successful before we do anything else.
    # Status code '200 OK'.
    if payload._status_code == 200:
        deploy_result = tasks.code_update.delay(request.json)


def post_post_sites_callback(request, payload):
    """
    Post callback for POST to `site` endpoint.

    Provision an instance.

    :param request: original flask.request object
    :param payload: response payload
    """
    if payload._status_code == 201:
        app.logger.debug(payload.data)
        payload_data = json.loads(payload.data)
        # Convert payload to list.
        if not isinstance(payload_data, list):
            payload_data = [payload_data]
        app.logger.debug(payload_data)
        for site in payload_data:
            app.logger.debug(site)
            # Need the rest of the Site object to see if this is Express.
            query = 'where={{"_id":"{0}"}}'.format(site['_id'])
            site = utilities.get_eve('sites', query)
            site = site['_items'][0]
            app.logger.debug(site)
            if site['type'] == 'express':
                # Assign an sid, an update group, any missing code, and date fields.
                site['sid'] = 'p1' + sha1(site['_id']).hexdigest()[0:10]
                site['update_group'] = random.randint(0, 2)
                # Add default core and profile if not set.
                # The 'get' method checks if the key exists.
                if not site['code'].get('core'):
                    query = 'where={{"meta.name":"{0}","meta.code_type":"core","meta.is_current":true}}'.format(default_core)
                    core_get = utilities.get_eve('code', query)
                    app.logger.debug(core_get)
                    site['code']['core'] = core_get['_items'][0]['_id']
                if not site['code'].get('profile'):
                    query = 'where={{"meta.name":"{0}","meta.code_type":"profile","meta.is_current":true}}'.format(default_profile)
                    profile_get = utilities.get_eve('code', query)
                    app.logger.debug(profile_get)
                    site['code']['profile'] = profile_get['_items'][0]['_id']
                date_json = '{{"created":"{0}","update":"{1}"}}'.format(site['_created'], site['_updated'])
                site['dates'] = json.loads(date_json)
                # Ready to provision.
                app.logger.debug('Ready to send to Celery\n{0}'.format(site))
                tasks.site_provision.delay(site)


def post_patch_sites_callback(request, payload):
    """
    Post callback for PATCH to `site` endpoint.

    Provision an instance.

    :param request: original flask.request object
    :param payload: response payload
    """
    if payload._status_code == 201:
        app.logger.debug(payload.data)
        payload_data = json.loads(payload.data)
        # Convert payload to list.
        if not isinstance(payload_data, list):
            payload_data = [payload_data]
        app.logger.debug(payload_data)
        for site in payload_data:
            app.logger.debug(site)
            # Need the rest of the Site object to see if this is Express.
            query = 'where={{"_id":"{0}"}}'.format(site['_id'])
            site = utilities.get_eve('sites', query)
            site = site['_items'][0]
            app.logger.debug(site)
            if site['type'] == 'express':
                # Assign an sid, an update group, any missing code, and date fields.
                site['sid'] = 'p1' + sha1(site['_id']).hexdigest()[0:10]
                site['update_group'] = random.randint(0, 2)
                # Add default core and profile if not set.
                # The 'get' method checks if the key exists.
                if not site['code'].get('core'):
                    query = 'where={{"meta.name":"{0}","meta.code_type":"core","meta.is_current":true}}'.format(default_core)
                    core_get = utilities.get_eve('code', query)
                    app.logger.debug(core_get)
                    site['code']['core'] = core_get['_items'][0]['_id']
                if not site['code'].get('profile'):
                    query = 'where={{"meta.name":"{0}","meta.code_type":"profile","meta.is_current":true}}'.format(default_profile)
                    profile_get = utilities.get_eve('code', query)
                    app.logger.debug(profile_get)
                    site['code']['profile'] = profile_get['_items'][0]['_id']
                app.logger.debug(site)
                date_json = '{{"created":"{0}","update":"{1}"}}'.format(site['_created'], site['_updated'])
                site['dates'] = json.loads(date_json)
                # Ready to provision.
                app.logger.debug('Got to fabric\n{0}'.format(site))
                tasks.site_provision.delay(site)


def post_get_command_callback(request, payload):
    """
    Post callback for GET to `command` endpoint.

    Run commands when API endpoints are called.

    :param request: original flask.request object
    :param payload: response payload
    :return:
    """
    tasks.command_run.delay(request.json)


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


# TODO: Add in a message (DONE) and better result broker, I don't want to use the DB. It is currently 41 GB for inventory.


"""
Setup the application and logging.
"""
# Tell Eve to use Basic Auth and where our data structure is defined.
app = Eve(auth=utilities.AtlasBasicAuth, settings="/data/code/atlas/config_data_structure.py")
# TODO: Remove debug mode.
app.debug = True

# Add specific callbacks
# Pattern is: `atlas.on_{Hook}_{Method}_{Resource}`
app.on_pre_POST += pre_post_callback
app.on_pre_POST_code += pre_post_code_callback
app.on_pre_PATCH_code += pre_patch_code_callback
app.on_post_POST += post_post_callback
app.on_post_POST_code += post_post_code_callback
app.on_post_POST_sites += post_post_sites_callback
app.on_post_PATCH_code += post_patch_code_callback
app.on_post_GET_command += post_get_command_callback


if __name__ == '__main__':
    # Enable logging to 'atlas.log' file
    # TODO: Figure out why the stuff shows in the apache error log, not this location.
    handler = logging.FileHandler('atlas.log')
    # The default log level is set to WARNING, so we have to explicitly set the
    # logging level to Debug.
    app.logger.setLevel(logging.DEBUG)
    # Append the handler to the default application logger
    app.logger.addHandler(handler)

    # This goes last.
    app.run(host='0.0.0.0', ssl_context='adhoc')
