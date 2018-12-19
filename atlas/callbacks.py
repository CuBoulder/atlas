"""
Callbacks for Eve event hooks.
"""
import logging
import random
import json
from hashlib import sha1

from flask import abort, g
from bson import ObjectId
from celery import chord

from atlas import tasks
from atlas import utilities
from atlas.config import (ATLAS_LOCATION, DEFAULT_CORE, DEFAULT_PROFILE, SERVICE_ACCOUNT_USERNAME,
                          PROTECTED_PATHS, BASE_URLS, ENVIRONMENT)

# Setup a sub-logger. See tasks.py for longer comment.
log = logging.getLogger('atlas.callbacks')


# Callbacks
def pre_post(resource, request):
    """
    :param resource: resource accessed
    :param request: flask.request object
    """
    log.debug('POST | Resource - %s | Request - %s, | request.data - %s',
              resource, str(request), request.data)


def pre_post_sites(request):
    """
    :param request: flask.request object
    """
    log.debug('sites | POST | Pre post callback')
    # Check to see if we have a current profile and core.
    core = utilities.get_current_code(name=DEFAULT_CORE, code_type='core')
    log.debug('sites | POST | Pre post callback | core | %s', core)
    profile = utilities.get_current_code(name=DEFAULT_PROFILE, code_type='profile')
    log.debug('sites | POST | Pre post callback | profile | %s', profile)

    if not core and not profile:
        log.error('sites | POST | Pre post callback | No current core or profile')
        abort(409, 'Error: There is no current core or profile.')
    elif not core:
        log.error('sites | POST | Pre post callback | No current core')
        abort(409, 'Error: There is no current core.')
    elif not profile:
        log.error('sites | POST | Pre post callback | No current profile')
        abort(409, 'Error: There is no current profile.')

    # Check for a protected path.
    if json.loads(request.data).get('path') and json.loads(request.data)['path'] in PROTECTED_PATHS:
        log.error('sites | POST | Pre post callback | Protected path')
        abort(409, 'Error: Cannot use this path, it is on the protected list.')

    # Check for a protected path.
    if json.loads(request.data).get('path') and json.loads(request.data)['path'] in PROTECTED_PATHS:
        log.error('sites | POST | Pre post callback | Protected path')
        abort(409, 'Error: Cannot use this path, it is on the protected list.')


def pre_patch_sites(request, payload):
    """
    :param request: flask.request object
    """
    log.debug('sites | PATCH | Pre patch callback | Payload - %s', payload)

    # Check for a protected path.
    if 'path' in json.loads(request.data) and json.loads(request.data)['path'] in PROTECTED_PATHS:
        log.error('sites | PATCH | Pre patch callback | Protected path')
        abort(409, 'Error: Cannot use this path, it is on the protected list.')


def pre_put_sites(request, payload):
    """
    :param request: flask.request object
    """
    log.debug('sites | PUT | Pre put callback | Payload - %s', payload)

    # Check for a protected path.
    if 'path' in json.loads(request.data) and json.loads(request.data)['path'] in PROTECTED_PATHS:
        log.error('sites | PUT | Pre put callback | Protected path')
        abort(409, 'Error: Cannot use this path, it is on the protected list.')


def pre_delete_code(request, lookup):
    """
    Make sure no sites are using the code.

    :param request: flask.request object
    :param lookup:
    """
    code = utilities.get_single_eve('code', lookup['_id'])
    log.debug('code | Delete | code - %s', code)

    # Check for sites using this piece of code.
    if code['meta']['code_type'] in ['module', 'theme', 'library']:
        code_type = 'package'
    else:
        code_type = code['meta']['code_type']
    log.debug('code | Delete | code - %s | code_type - %s', code['_id'], code_type)
    site_query = 'where={{"code.{0}":"{1}"}}'.format(code_type, code['_id'])
    sites = utilities.get_eve('sites', site_query)
    log.debug('code | Delete | code - %s | sites result - %s', code['_id'], sites)
    if not sites['_meta']['total'] == 0:
        site_list = []
        for site in sites['_items']:
            # Create a list of sites that use this code item.
            # If 'sid' is a key in the site dict use it, otherwise use '_id'.
            if site.get('sid'):
                site_list.append(site['sid'])
            else:
                site_list.append(site['_id'])
        site_list_full = ', '.join(site_list)
        log.error('code | Delete | code - %s | Code item is in use by one or more sites - %s',
                  code['_id'], site_list_full)
        abort(409, 'A conflict happened while processing the request. Code item is in use by one or more sites.')


def on_insert_sites(items):
    """
    Assign a sid, an update group, db_key, any missing code, and date fields.

    :param items: List of dicts for items to be created.
    """
    log.debug(items)
    for item in items:
        log.debug(item)
        if 'sid' not in item:
            item['sid'] = 'p1' + sha1(utilities.randomstring()).hexdigest()[0:10]
        if 'path' not in item:
            item['path'] = item['sid']
        if 'update_group' not in item:
            item['update_group'] = random.randint(0, 2)
        # Add default core and profile if not set.
        # The 'get' method checks if the key exists.
        if 'code' in item:
            if 'core' not in item['code']:
                item['code']['core'] = ObjectId(utilities.get_current_code(
                    name=DEFAULT_CORE, code_type='core'))
            if 'profile' not in item['code']:
                item['code']['profile'] = ObjectId(utilities.get_current_code(
                    name=DEFAULT_PROFILE, code_type='profile'))
        else:
            item['code'] = {}
            item['code']['core'] = ObjectId(utilities.get_current_code(
                name=DEFAULT_CORE, code_type='core'))
            item['code']['profile'] = ObjectId(utilities.get_current_code(
                name=DEFAULT_PROFILE, code_type='profile'))
        date_json = '{{"created":"{0} GMT"}}'.format(item['_created'])
        item['dates'] = json.loads(date_json)


def on_inserted_sites(items):
    """
    Provision Express instances.

    :param items: List of dicts for instances to be provisioned.
    """
    log.debug('site | Site objects created | sites - %s', items)
    for item in items:
        log.debug(item)
        log.debug('site | Site object created | site - %s', item)
        # Create statistics item
        statistics_payload = {}
        # Need to get the string out of the ObjectID.
        statistics_payload['site'] = str(item['_id'])
        log.debug('site | Create Statistics item - %s', statistics_payload)
        statistics = utilities.post_eve(resource='statistics', payload=statistics_payload)
        item['statistics'] = str(statistics['_id'])

        tasks.site_provision.delay(item)


def on_insert_code(items):
    """
    Deploy code onto servers as the items are created.

    If a new code item 'is_current', PATCH 'is_current' code with the same name
    and type to no longer be current.

    :param items: List of dicts for items to be created.
    """
    log.debug('code | Insert | items - %s', items)
    for item in items:
        log.debug('code | POST | On Insert callback | %s', item)
        # Check to see if we have a current profile and core.
        code_query = 'where={{"meta.name":"{0}","meta.version":"{1}","meta.code_type":"{2}"}}'.format(item['meta']['name'], item['meta']['version'], item['meta']['code_type'])
        code = utilities.get_eve('code', code_query)
        log.debug('code | POST | On Insert callback | Code query result | %s', code)
        if not code['_meta']['total'] == 0:
            log.error('code | POST | On Insert callback | %s named %s-%s already exists', item['meta']['code_type'], item['meta']['name'], item['meta']['version'])
            abort(409, 'Error: A {0} named {1}-{2} already exists.'.format(item['meta']['code_type'], item['meta']['name'], item['meta']['version']))

        if item.get('meta') and item['meta'].get('is_current') and item['meta']['is_current'] is True:
            query = 'where={{"meta.name":"{0}","meta.code_type":"{1}","meta.is_current": true}}'.format(item['meta']['name'], item['meta']['code_type'])
            code_get = utilities.get_eve('code', query)
            log.debug('code | Insert | current code - %s', code_get)
            if code_get['_meta']['total'] != 0:
                for code in code_get['_items']:
                    request_payload = {'meta.is_current': False}
                    utilities.patch_eve('code', code['_id'], request_payload)
        log.debug('code | Insert | Ready to deploy item - %s', item)
        tasks.code_deploy.delay(item)


def pre_delete_sites(request, lookup):
    """
    Remove site from servers right before the item is removed.

    :param request: flask.request object
    :param lookup:
    """
    log.debug('Instances | Pre Delete | lookup - %s', lookup)
    instance = utilities.get_single_eve('sites', lookup['_id'])
    log.debug('Instances | Pre Delete | instance - %s', instance)

    # Check if instance is launched.
    if not instance['status'] in ['launched', 'launching']:
        log.debug('Instances | Pre Delete | instance - %s | Instance state - %s | Okay to delete', instance, instance['status'])
        tasks.site_remove.delay(instance)
    else:
        log.error('Instances | Delete | instance - %s | Instance is launched or launching',
                  instance['_id'])
        abort(409, 'Instance is launched or launching. To delete, take instance down first.')


def on_delete_item_code(item):
    """
    Remove code from servers right before the item is removed.

    :param item:
    """
    log.debug('code | on delete | item - %s', item)
    other_static_assets = False
    if item['meta']['code_type'] == 'static':
        query = 'where={{"meta.name":"{0}","meta.code_type":"static","_id":{{"$ne":"{1}"}}}}'.format(
            item['meta']['name'], item['_id'])
        code = utilities.get_eve('code', query)
        if code['_meta']['total'] != 0:
            other_static_assets = True
    log.info('code | on delete | other static assets - %s', other_static_assets)
    tasks.code_remove.delay(item, other_static_assets)


def on_delete_item_backup(item):
    """
    Remove backup from servers right before the item is removed.

    :param item:
    """
    log.debug('Backup | on delete | item - %s', item)
    tasks.backup_remove.delay(item)


def on_update_code(updates, original):
    """
    Update code on the servers as the item is updated.

    :param updates:
    :param original:
    """
    log.debug('code | on update | updates - %s | original - %s', updates, original)
    # If this 'is_current' PATCH code with the same name and code_type.
    if updates.get('meta') and updates['meta'].get('is_current') and updates['meta']['is_current'] is True:
        # If the name and code_type are not changing, we need to load them from the original.
        name = updates['meta']['name'] if updates['meta'].get('name') else original['meta']['name']
        code_type = updates['meta']['code_type'] if updates['meta'].get('code_type') else original['meta']['code_type']

        query = 'where={{"meta.name":"{0}","meta.code_type":"{1}","meta.is_current": true,"_id":{{"$ne":"{2}"}}}}'.format(
            name, code_type, original['_id'])
        code_get = utilities.get_eve('code', query)
        log.debug('code | on update | Current code - %s', code_get)

        for code in code_get['_items']:
            request_payload = {'meta.is_current': False}
            utilities.patch_eve('code', code['_id'], request_payload)

    # We need the whole record so that we can manipulate code in the right place.
    # Copy 'original' to a new dict, then update it with values from 'updates' to create an item to
    # deploy. Need to do the same process for meta first, otherwise the update will fully overwrite.
    if updates.get('meta'):
        meta = original['meta'].copy()
        meta.update(updates['meta'])
    updated_item = original.copy()
    updated_item.update(updates)
    if updates.get('meta'):
        updated_item['meta'] = meta

    if updates.has_key('meta') and (updates['meta'].has_key('name') or updates['meta'].has_key('version') or updates['meta'].has_key('code_type')):
        update_code = True
    elif updates.has_key('commit_hash') or updates.has_key('git_url'):
        update_code = True
    else:
        update_code = False

    if update_code:
        log.debug('code | on update | Ready to hand to Celery')
        # chord two tasks
        chord(tasks.code_update.s(updated_item, original), tasks.clear_php_cache.si())()


def on_update_sites(updates, original):
    """
    Update an instance.

    :param updates:
    :param original:
    """
    log.debug('sites | Update | Updates - %s | Original - %s', updates, original)
    site = original.copy()
    site.update(updates)
    # Only need to rewrite the nested dicts if they got updated.
    if updates.get('code'):
        code = original['code'].copy()
        code.update(updates['code'])
        site['code'] = code
    if updates.get('dates') and original.get('dates'):
        dates = original['dates'].copy()
        dates.update(updates['dates'])
        site['dates'] = dates
    if updates.get('settings'):
        settings = original['settings'].copy()
        settings.update(updates['settings'])
        site['settings'] = settings

    if updates.get('status'):
        if updates['status'] in ['installing', 'launching', 'take_down', 'restore']:
            if updates['status'] == 'installing':
                date_json = '{{"assigned":"{0} GMT"}}'.format(updates['_updated'])
            elif updates['status'] == 'launching':
                date_json = '{{"launched":"{0} GMT"}}'.format(updates['_updated'])
            elif updates['status'] == 'locked':
                date_json = '{{"locked":""}}'
            elif updates['status'] == 'take_down':
                date_json = '{{"taken_down":"{0} GMT"}}'.format(updates['_updated'])
            elif updates['status'] == 'restore':
                date_json = '{{"restored":"{0} GMT"}}'.format(updates['_updated'])

            updates['dates'] = json.loads(date_json)

    log.debug('sites | Update | Ready for Celery | Site - %s | Updates - %s', site, updates)
    tasks.site_update.delay(site=site, updates=updates, original=original)


def on_updated_code(updates, original):
    """
    Find instances that use this code asset and re-add them.

    :param updates:
    :param original:
    """
    log.debug('code | on updated | updates - %s | original - %s', updates, original)
    # First get the code_type from either the update or original, then convert package types for
    # querying instance objects.
    if updates.get('meta') and updates['meta'].get('code_type'):
        code_type = updates['meta']['code_type']
    else:
        code_type = original['meta']['code_type']
    if code_type in ['module', 'theme', 'library']:
        code_type = 'package'

    if updates.has_key('meta'):
        if updates['meta']['name'] != original['meta']['name'] or updates['meta']['version'] != original['meta']['version'] or updates['meta']['code_type'] != original['meta']['code_type']:
            update_sites = True
            log.debug('code | on updated | Found meta data changes | %s', updates['meta'])
        else:
            log.debug('code | on updated | Found no meta changes that require an update')
            update_sites = False
    elif updates.has_key('commit_hash') or updates.has_key('git_url'):
        update_sites = True
        log.debug('code | on updated | Found git data changes')
    else:
        log.debug('code | on updated | Found no changes')
        update_sites = False

    if update_sites:
        log.info('Code | on updated | Preparing to update instances')
        query = 'where={{"code.{0}":"{1}"}}'.format(code_type, original['_id'])
        sites_get = utilities.get_eve('sites', query)

        if sites_get['_meta']['total'] is not 0:
            for site in sites_get['_items']:
                log.debug('code | on updated | site - %s', site)
                code_id_string = site['code'][code_type]
                payload = {'code': {code_type: code_id_string}}
                log.debug('code | on updated | payload - %s', payload)
                utilities.patch_eve('sites', site['_id'], payload)


# Update user fields on all events. If the update is coming from Drupal, it
# will use the client_username for authentication and include the field for
# us. If someone is querying the API directly, they will user their own
# username and we need to add that.
def pre_insert(resource, items):
    """
    On POST, get the username from the request and add it to the record.
    """
    username = g.get('username', None)
    if username is not None:
        for item in items:
            item['created_by'] = username
            item['modified_by'] = username


def pre_update(resource, updates, original):
    """
    On PATCH, get the username from the request and add it to the record if one was not provided.
    """
    # Only update if a username was not provided.
    if not updates.get('modified_by'):
        username = g.get('username', None)
        if username is not None:
            if username is not SERVICE_ACCOUNT_USERNAME:
                updates['modified_by'] = username


def pre_replace(resource, item, original):
    """
    On PUT, get the username from the request and add it to the record if one was not provided.
    """
    # Only update if a username was not provided.
    if not item.get('modified_by'):
        username = g.get('username', None)
        if username is not None:
            if username is not SERVICE_ACCOUNT_USERNAME:
                item['modified_by'] = username


def on_delete_item(resource, item):
    """
    On DELETE, get the username from the request and add it to the record if one was not provided.
    """
    # Only update if a username was not provided.
    log.debug('On Delete | Update modified user')
    username = g.get('username', None)
    if username is not None:
        item['modified_by'] = username


def on_deleted_item_sites(item):
    """
    After the DELETE, notify slack
    """
    slack_text = 'Site Remove - Success - {0}/{1}'.format(BASE_URLS[ENVIRONMENT], item['path'])
    slack_color = 'good'
    slack_link = '{0}/{1}'.format(BASE_URLS[ENVIRONMENT], item['path'])

    slack_payload = {
        "text": slack_text,
        "attachments": [
            {
                "fallback": slack_text,
                "color": slack_color,
                "fields": [
                    {"title": "Instance", "value": slack_link, "short": False},
                    {"title": "Environment", "value": ENVIRONMENT, "short": True},
                    {"title": "Delete requested by", "value": item['modified_by'], "short": True}
                ],
            }
        ],
    }
    utilities.post_to_slack_payload(slack_payload)
