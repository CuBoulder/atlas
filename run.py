import sys
import logging
import random
import json

from eve import Eve
from flask import abort, jsonify
from hashlib import sha1
from atlas import tasks
from atlas import utilities
from atlas.config import *


path = '/data/code'
if path not in sys.path:
    sys.path.append(path)

# Required for MVP
# TODO: PATCH for site
# TODO: DELETE for site
# TODO: POST for command
# TODO: GET for command
# TODO: DELETE for a command.
# TODO: Create requirements.txt
# TODO: Add a Package.
# TODO: Change the name of a code package.

# Nice to have
# TODO: Make Atlas autodiscover resources
# TODO: Test for failure to add package and revert the PATCH of the site item.

# Backlog
# TODO: Add support for switching profiles.
# TODO: Convert 'installed' to 'assigned', 'assigned_training'.
# TODO: Validate that each code type is correct. IE no core as a profile.
# TODO: Figure out how to do redirects and path changes
# TODO: Figure out how to test
# TODO: Support sites without a profile. Check if default profile is set.
# TODO: Add support for DNS entries that are owned as part of a site.
# TODO: Consider adding additional field to 'code' for 'has_submodules'. This would allow us to improve performance of code checkouts.


# Callbacks
def pre_post_callback(resource, request):
    """
    :param resource: resource accessed
    :param request: flask.request object
    """
    app.logger.debug('POST to {0} resource\nRequest:\n{1}'.format(resource, request.json))


def pre_delete_code_callback(request, lookup):
    """
    Make sure no sites are using the code.

    :param request: flask.request object
    :param lookup:
    """
    code = utilities.get_single_eve('code', lookup['_id'])
    app.logger.debug(code)
    site_query = 'where={{"code.{0}":"{1}"}}'.format(code['meta']['code_type'], code['_id'])
    sites = utilities.get_eve('sites', site_query)
    app.logger.debug(sites)
    if not sites['_meta']['total'] == 0:
        for site in sites['_items']:
            # Create a list of sites that use this code item.
            # If 'sid' is a key in the site dict use it, otherwise use '_id'.
            site_ids = site_ids + site['sid'] if site.get('sid') else site['_id'] + '\n'
        app.logger.error('Code item is in use by one or more sites:\n{0}'.format(site_ids))
        abort(409, 'A conflict happened while processing the request. Code item is in use by one or more sites.')


def on_fetched_item_command_callback(response):
    """
    Run commands when API endpoints are called.

    :param response:
    """
    app.logger.debug('Ready to send to Celery\n{0}'.format(item))
    tasks.command_run.delay(response)


def on_insert_sites_callback(items):
    """
    Assign a sid, an update group, db_key, any missing code, and date fields.

    :param items: List of dicts for items to be created.
    """
    app.logger.debug(items)
    for item in items:
        app.logger.debug(item)
        if item['type'] == 'express':
            item['sid'] = 'p1' + sha1(utilities.randomstring()).hexdigest()[0:10]
            item['path'] = item['sid']
            item['update_group'] = random.randint(0, 2)
            # Add default core and profile if not set.
            # The 'get' method checks if the key exists.
            if not item['code'].get('core'):
                query = 'where={{"meta.name":"{0}","meta.code_type":"core","meta.is_current":true}}'.format(default_core)
                core_get = utilities.get_eve('code', query)
                app.logger.debug(core_get)
                item['code']['core'] = core_get['_items'][0]['_id']
            # TODO: Support sites without a profile. Check if default profile is set or not.
            if not item['code'].get('profile'):
                query = 'where={{"meta.name":"{0}","meta.code_type":"profile","meta.is_current":true}}'.format(default_profile)
                profile_get = utilities.get_eve('code', query)
                app.logger.debug(profile_get)
                # TODO: Error if there is no current code.
                item['code']['profile'] = profile_get['_items'][0]['_id']
            date_json = '{{"created":"{0} GMT"}}'.format(item['_created'])
            item['dates'] = json.loads(date_json)
            app.logger.debug('Ready to send to create item\n{0}'.format(item))


def on_inserted_sites_callback(items):
    """
    Provision Express instances.

    :param items: List of dicts for instances to be provisioned.
    """
    app.logger.debug(items)
    for item in items:
        app.logger.debug(item)
        if item['type'] == 'express':
            app.logger.debug('Ready to send to Celery\n{0}'.format(item))
            tasks.site_provision.delay(item)


def on_insert_code_callback(items):
    """
    Deploy code onto servers as the items are created.

    If a new code item 'is_current', PATCH 'is_current' code with the same name
    and type to no longer be current.

    :param items: List of dicts for items to be created.
    """
    app.logger.debug(items)
    for item in items:
        if item.get('meta') and item['meta'].get('is_current') and item['meta']['is_current'] == True:
            # Need a lowercase string when querying boolean values. Python
            # stores it as 'True'.
            query = 'where={{"meta.name":"{0}","meta.code_type":"{1}","meta.is_current": {2}}}'.format(item['meta']['name'], item['meta']['code_type'], str(item['meta']['is_current']).lower())
            code_get = utilities.get_eve('code', query)
            app.logger.debug(code_get)
            for code in code_get['_items']:
                request_payload = {'meta.is_current': False}
                utilities.patch_eve('code', code['_id'], request_payload)
        app.logger.debug('Ready to send to Celery\n{0}'.format(item))
        tasks.code_deploy.delay(item)

def on_delete_item_code_callback(item):
    """
    Remove code from servers right before the item is removed.

    :param item:
    """
    app.logger.debug(item)
    tasks.code_remove.delay(item)


def on_update_code_callback(updates, original):
    """
    Update code on the servers as the item is updated.

    :param updates:
    :param original:
    """
    app.logger.debug(updates)
    app.logger.debug(original)
    # If this 'is_current' PATCH code with the same name and code_type.
    if updates.get('meta') and updates['meta'].get('is_current') and updates['meta']['is_current'] == True:
        # If the name and code_type are not changing, we need to load them from
        # the original.
        name = updates['meta']['name'] if updates['meta'].get('name') else original['meta']['name']
        code_type = updates['meta']['code_type'] if updates['meta'].get('code_type') else original['meta']['code_type']

        query = 'where={{"meta.name":"{0}","meta.code_type":"{1}","meta.is_current": {2}}}'.format(name, code_type, str(updates['meta']['is_current']).lower())
        code_get = utilities.get_eve('code', query)
        # TODO: Filter out the site we are updating.
        app.logger.debug(code_get)

        for code in code_get['_items']:
            request_payload = {'meta.is_current': False}
            utilities.patch_eve('code', code['_id'], request_payload)

    # We need the whole record so that we can manipulate code in the right
    # place.
    # Copy 'original' to a new dict, then update it with values from 'updates'
    # to create an item to deploy. Need to do the same process for meta first,
    # otherwise the update will fully overwrite.
    meta = original['meta'].copy()
    meta.update(updates['meta'])
    item = original.copy()
    item.update(updates)
    item['meta'] = meta

    app.logger.debug('Ready to hand to Celery\n{0}'.format(item))
    tasks.code_update.delay(item)


# TODO: Verify that updated has the same arguments.
def on_updated_sites_callback(updates, original):
    """
    Update an instance.

    :param updates:
    :param original:
    """
    app.logger.debug(updates)
    app.logger.debug(original)
    site_type = updates['type'] if updates.get('type') else original['type']
    if site_type == 'express':
        item = original.copy()
        item.update(updates)
        # Only need to rewrite the nested dicts if they got updated.
        if updates.get('code'):
            code = original['code'].copy()
            code.update(updates['code'])
            item['code'] = code
        if updates.get('dates'):
            dates = original['dates'].copy()
            dates.update(updates['dates'])
            item['dates'] = dates

        app.logger.debug('Ready to hand to Celery\n{0}'.format(item))
        tasks.site_update.delay(item, updates, original)


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

# Specific callbacks. Pattern is: `atlas.on_{Hook}_{Method}_{Resource}`
# Use pre event hooks if there is a chance you want to abort.
# Use DB hooks if you want to modify data on the way in.
app.on_pre_POST += pre_post_callback
app.on_pre_DELETE_code += pre_delete_code_callback
app.on_fetched_item_command += on_fetched_item_command_callback
app.on_insert_code += on_insert_code_callback
app.on_insert_sites += on_insert_sites_callback
app.on_inserted_sites += on_inserted_sites_callback
app.on_update_code += on_update_code_callback
app.on_updated_sites += on_updated_sites_callback
app.on_delete_item_code += on_delete_item_code_callback


@app.errorhandler(409)
def custom409(error):
    response = jsonify({'message': error.description})
    response.status_code = 409
    return response


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
