"""
    atlas.tasks
    ~~~~~~
    Celery tasks for Atlas.
"""
import os
import time
import json

from datetime import datetime, timedelta
from collections import Counter
from bson import json_util
from math import ceil
from random import randint
import requests
from celery import Celery, chord
from celery.utils.log import get_task_logger
from fabric.api import execute
from git import GitCommandError

from atlas import fabric_tasks, utilities, config_celery
from atlas import code_operations, instance_operations, backup_operations
from atlas.config import (ENVIRONMENT, WEBSERVER_USER, DESIRED_SITE_COUNT, EMAIL_HOST,
                          SSL_VERIFICATION, CODE_ROOT, BACKUPS_LARGE_INSTANCES)
from atlas.config_servers import (BASE_URLS, API_URLS)

# Setup a sub-logger
# Best practice is to setup sub-loggers rather than passing the main logger between different parts of the application.
# https://docs.python.org/3/library/logging.html#logging.getLogger and
# https://stackoverflow.com/questions/39863718/how-can-i-log-outside-of-main-flask-module
log = get_task_logger(__name__)

# Create the Celery app object
celery = Celery('tasks')
celery.config_from_object(config_celery)


class CronException(Exception):
    def __init__(self, message, errors):

        # Call the base class constructor with the parameters it needs
        super(CronException, self).__init__(message)

        # Now for your custom code...
        self.errors = errors

        log.debug('Cron Error | %s', self.errors)
        # Expand the list to the variables we need.
        fabric_result, site_path = self.errors

        log.debug(fabric_result)
        # The fabric_result is a dict of {hosts: result} from fabric.
        # We loop through each row and add it to a new dict if value is not
        # None.
        # This uses constructor syntax https://doughellmann.com/blog/2012/11/12/the-performance-impact-of-using-dict-instead-of-in-cpython-2-7-2/.
        errors_for_slack = {k: v for k, v in fabric_result.iteritems() if v is not None}

        instance_url = '{0}/{1}'.format(BASE_URLS[ENVIRONMENT], site_path)
        title = 'Run Command'
        instance_link = '<' + instance_url + '|' + instance_url + '>'
        command = 'drush elysia-cron run'.format(WEBSERVER_USER)
        user = 'Celerybeat'

        # Only post if an error
        if errors_for_slack:
            text = 'Error'
            slack_color = 'danger'
            slack_channel = 'cron-errors'

            slack_fallback = instance_url + ' - ' + ENVIRONMENT + ' - ' + command

            slack_payload = {
                # Channel will be overridden on local ENVIRONMENTs.
                "channel": slack_channel,
                "text": text,
                "attachments": [
                    {
                        "fallback": slack_fallback,
                        "color": slack_color,
                        "author_name": user,
                        "title": title,
                        "fields": [
                            {
                                "title": "Instance",
                                "value": instance_link,
                                "short": True
                            },
                            {
                                "title": "Environment",
                                "value": ENVIRONMENT,
                                "short": True
                            },
                            {
                                "title": "Command",
                                "value": command,
                                "short": True
                            }
                        ],
                    }
                ],
                "user": user
            }

            error_json = json.dumps(errors)
            slack_payload['attachments'].append(
                {
                    "fallback": 'Error message',
                    # A lighter red.
                    "color": '#ee9999',
                    "fields": [
                        {
                            "title": "Error message",
                            "value": error_json,
                            "short": False
                        }
                    ]
                }
            )
            utilities.post_to_slack_payload(slack_payload)
    pass


@celery.task
def code_deploy(item):
    """
    Deploy git repositories to the appropriate places.

    :param item: The flask request.json object.
    :return:
    """
    log.debug('Code deploy | %s', item)
    try:
        clone = code_operations.repository_clone(item)
    except GitCommandError:
        log.error('Code | Clone | Cannot clone repository, check URL.')
    try:
        checkout = code_operations.repository_checkout(item)
    except GitCommandError:
        log.error('Code | Checkout | Cannot checkout requested tag, check value.')
    if item['meta']['is_current']:
        code_operations.update_symlink_current(item)
        log.debug('Code deploy | Symlink | Is current')
    
    if item['meta']['code_type'] == 'static':
        code_operations.deploy_static(item)

    sync = code_operations.sync_code()

    if clone or sync:
        text = 'Error'
        slack_color = 'danger'
    else:
        text = 'Success'
        slack_color = 'good'

    slack_fallback = '{0} - {1}'.format(item['meta']['name'], item['meta']['version'])

    slack_payload = {

        "text": 'Code Deploy',
        "attachments": [
            {
                "fallback": slack_fallback,
                "color": slack_color,
                "fields": [
                    {
                        "title": "Environment",
                        "value": ENVIRONMENT,
                        "short": True
                    },
                    {
                        "title": "User",
                        "value": item['created_by'],
                        "short": True
                    },
                    {
                        "title": "Name",
                        "value": item['meta']['name'],
                        "short": True
                    },
                    {
                        "title": "Version",
                        "value": item['meta']['version'],
                        "short": True
                    }

                ],
            }
        ],
        "user": item['created_by']
    }

    if clone or sync:
        error_json = json.dumps(clone + sync)
        slack_payload['attachments'].append(
            {
                "fallback": 'Error message',
                # A lighter red.
                "color": '#ee9999',
                "fields": [
                    {
                        "title": "Error message",
                        "value": error_json,
                        "short": False
                    }
                ]
            }
        )

    utilities.post_to_slack_payload(slack_payload)


@celery.task
def code_update(updated_item, original_item):
    """
    Update code checkout.

    :param updated_item:
    :param original_item:
    :return:
    """
    log.debug('Code update | Updates - %s', updated_item)
    # Set up some authoritative values
    final_item = original_item.copy()
    # updated_item has the correct meta dict
    final_item.update(updated_item)

    if (updated_item['meta']['name'] != original_item['meta']['name']) or (updated_item['meta']['version'] != original_item['meta']['version']) or (updated_item['meta']['code_type'] != original_item['meta']['code_type']):
        code_operations.repository_remove(original_item)
        clone = code_operations.repository_clone(final_item)
        log.debug('Code Update | Clone | %s', clone)

    checkout = code_operations.repository_checkout(final_item)
    log.debug('Code deploy | Checkout | %s', checkout)
    if original_item['meta']['is_current']:
        code_operations.update_symlink_current(original_item)
        log.debug('Code deploy | Symlink | Is current')

    if final_item['meta']['code_type'] == 'static':
        code_operations.deploy_static(final_item)

    sync = code_operations.sync_code()

    slack_title = 'Code Update - Success'
    slack_color = 'good'

    slack_payload = {
        "text": slack_title,
        "attachments": [
            {
                "fallback": slack_title,
                "color": slack_color,
                "fields": [
                    {
                        "title": "Environment",
                        "value": ENVIRONMENT,
                        "short": True
                    },
                    {
                        "title": "User",
                        "value": final_item['created_by'],
                        "short": True
                    },
                    {
                        "title": "Name",
                        "value": final_item['meta']['name'],
                        "short": True
                    },
                    {
                        "title": "Version",
                        "value": final_item['meta']['version'],
                        "short": True
                    }
                ],
            }
        ],
    }
    utilities.post_to_slack_payload(slack_payload)


@celery.task
def code_remove(item, other_static_assets=True):
    """Remove code from the server.

    Arguments:
        item {dict} -- Item record for static asset to deploy

    Keyword Arguments:
        other_static_assets {bool} -- Only applies in cases with static assets. If false, remove
        directory for static asset name (default: {True})
    """

    log.info('Code remove | %s', item)
    code_operations.repository_remove(item)
    if item['meta']['is_current']:
        code_folder_current = '{0}/{1}/{2}/{2}-current'.format(
            CODE_ROOT,
            utilities.code_type_directory_name(item['meta']['code_type']),
            item['meta']['name'])
        os.unlink(code_folder_current)

    if item['meta']['code_type'] == 'static':
        code_operations.remove_static(item, other_static_assets)

    sync = code_operations.sync_code()
    execute(fabric_tasks.clear_php_cache)

    # Slack notification
    slack_title = 'Code Remove - Success'
    slack_color = 'good'

    slack_payload = {
        "text": slack_title,
        "attachments": [
            {
                "fallback": slack_title,
                "color": slack_color,
                "fields": [
                    {
                        "title": "Environment",
                        "value": ENVIRONMENT,
                        "short": True
                    },
                    {
                        "title": "User",
                        "value": item['created_by'],
                        "short": True
                    },
                    {
                        "title": "Name",
                        "value": item['meta']['name'],
                        "short": True
                    },
                    {
                        "title": "Version",
                        "value": item['meta']['version'],
                        "short": True
                    }
                ],
            }
        ],
    }
    utilities.post_to_slack_payload(slack_payload)


@celery.task
def code_heal(code_items):
    """
    Verify code is correctly deployed.
    """
    log.info('Heal | Code | Item - %s', code_items)
    # Setup a chord. Takes a 'group' (list of tasks that should be applied in parallel) and executes
    # another task after the group is complete.
    # In the second task, using .si creates an immutable signature so the return value of the
    # previous tasks will be ignored.
    task_group = chord((_code_heal.s(code) for code in code_items['_items']), _code_sync.si())()


@celery.task
def _code_heal(item):
    """
    Sub task for code_heal. Perform actual heal operations
    """
    if not os.path.isdir(utilities.code_path(item)):
        clone = code_operations.repository_clone(item)
        log.debug('Code heal | Clone | %s', clone)
    checkout = code_operations.repository_checkout(item)
    if item['meta']['is_current']:
        code_operations.update_symlink_current(item)
    log.debug('Code heal | Checkout | %s', checkout)


@celery.task
def _code_sync():
    """
    Sub task for code_heal. Sync healed code to server
    """
    sync = code_operations.sync_code()
    execute(fabric_tasks.clear_php_cache)


@celery.task
def site_provision(site):
    """
    Provision a new instance with the given parameters.

    :param site: A single site.
    :return:
    """
    log.info('Site provision | %s', site)
    start_time = time.time()
    # 'db_key' needs to be added here and not in Eve so that the encryption
    # works properly.
    site['db_key'] = utilities.encrypt_string(utilities.mysql_password())
    # Set future site status for settings file creation.
    if site['status'] == 'pending':
        site['status'] = 'available'

    try:
        log.debug('Site provision | Create database')
        utilities.create_database(site['sid'], site['db_key'])
    except Exception as error:
        log.error('Site provision failed | Database creation failed | %s', error)
        raise
    # Create instance with requested core, profile, and packages.
    try:
        instance_operations.instance_create(site)
    except Exception as error:
        log.error('Site provision failed | Error Message | %s', error)
        raise
    # Trigger rsync
    # ? Is a way to request a sync (w/ install chained)? Sync once when creating 5 instances
    log.info('Instance | Provision | Rsync')
    instance_operations.sync_instances(site['sid'])
    # Run install
    if site.get('install') and site['install'] is not False:
        try:
            execute(fabric_tasks.site_install, site=site)
        except Exception as error:
            log.error('Site install failed | Error Message | %s', error)
            raise
    # Correct file permissions
    instance_operations.correct_fs_permissions(site)
    instance_operations.sync_instances(site['sid'])

    # Update instance record
    patch_payload = {'status': site['status'],
                     'db_key': site['db_key'],
                     'statistics': site['statistics'],
                     'install': None}
    patch = utilities.patch_eve('sites', site['_id'], patch_payload)
    log.debug('Site provision | Patch | %s', patch)

    provision_time = time.time() - start_time
    log.info('Atlas operational statistic | Site Provision | %s', provision_time)

    # Slack notification
    profile = utilities.get_single_eve('code', site['code']['profile'])
    profile_string = profile['meta']['name'] + '-' + profile['meta']['version']

    core = utilities.get_single_eve('code', site['code']['core'])
    core_string = core['meta']['name'] + '-' + core['meta']['version']

    slack_title = 'Site provision - Success'
    slack_text = 'Site provision - Success - {0}/sites/{1}'.format(BASE_URLS[ENVIRONMENT], site['path'])
    slack_color = 'good'
    slack_link = '{0}/{1}'.format(BASE_URLS[ENVIRONMENT], site['path'])

    slack_payload = {
        "text": slack_text,
        "attachments": [
            {
                "fallback": slack_text,
                "color": slack_color,
                "fields": [
                    {
                        "title": "Instance",
                        "value": slack_link,
                        "short": False
                    },
                    {
                        "title": "Environment",
                        "value": ENVIRONMENT,
                        "short": True
                    },
                    {
                        "title": "Time",
                        "value": str(provision_time) + ' sec',
                        "short": True
                    },
                    {
                        "title": "Core",
                        "value": core_string,
                        "short": True
                    },
                    {
                        "title": "Profile",
                        "value": profile_string,
                        "short": True
                    },
                ],
            }
        ],
    }
    utilities.post_to_slack_payload(slack_payload)


@celery.task
def site_update(site, updates, original):
    """
    Update an instance with the given parameters.

    :param site: A complete site item, including new values.
    :param updates: A partial site item, including only changed keys.
    :param original: Complete original site item.
    :return:
    """
    log.debug('Site update | ID - %s | Site - %s | Updates - %s | Original - %s',
              site['_id'], site, updates, original)

    deploy_registry_rebuild = False
    deploy_update_database = False
    deploy_drupal_cache_clear = False
    deploy_php_cache_clear = False
    sync_instances = False

    if updates.get('code'):
        log.debug('Site update | ID - %s | Found code changes', site['_id'])
        # If we are updating code, we will need to sync instances
        sync_instances = True
        code_to_update = []
        if 'core' in updates['code']:
            log.debug('Site update | ID - %s | Found core change', site['_id'])
            instance_operations.switch_core(site)
            code_to_update.append(str(updates['code']['core']))
        if 'profile' in updates['code']:
            log.debug('Site update | ID - %s | Found profile change | Profile - %s', site['_id'],
                      str(updates['code']['profile']))
            instance_operations.switch_profile(site)
            code_to_update.append(str(updates['code']['profile']))
        if 'package' in updates['code']:
            log.debug('Site update | ID - %s | Found package changes', site['_id'])
            instance_operations.switch_packages(site)
            # Get a single string of all packages.
            for code in updates['code']['package']:
                code_to_update.append(str(code))
        if code_to_update:
            log.debug('Site update | ID - %s | Deploy | Code to update - %s', site['_id'],
                      code_to_update)
            code_query = 'where={{"_id":{{"$in":{0}}}}}'.format(json.dumps(code_to_update))
            log.debug('Site Update | ID - %s | Code query - %s', site['_id'], code_query)
            code_items = utilities.get_eve('code', code_query)
            log.debug('Site Update | ID - %s | Code query response - %s', site['_id'], code_items)
            for code in code_items['_items']:
                if code['deploy']['registry_rebuild']:
                    deploy_registry_rebuild = True
                if code['deploy']['update_database']:
                    deploy_update_database = True
                if code['deploy']['cache_clear']:
                    deploy_drupal_cache_clear = True
        # Email notification if we updated packages.
        if 'package' in updates['code']:
            package_name_string = ""
            for package in site['code']['package']:
                # Append the package name and a space.
                package_name_string += utilities.get_code_label(package) + ", "
            # Strip the trailing space off the end.
            package_name_string = package_name_string.rstrip()
            if len(package_name_string) > 0:
                subject = 'Package(s) added - {0}/{1}'.format(BASE_URLS[ENVIRONMENT], site['path'])
                message = "We added the requested packages to {0}/{1}.\n\n{2}\n\n - Web Express Team\n\nLogin to the site: {0}/{1}/user?destination=admin/settings/admin/bundle/list".format(BASE_URLS[ENVIRONMENT], site['path'], package_name_string)
            else:
                subject = 'Packages removed - {0}/{1}'.format(BASE_URLS[ENVIRONMENT], site['path'])
                message = "We removed all packages from {0}/{1}.\n\n - Web Express Team.".format(
                    BASE_URLS[ENVIRONMENT], site['path'])
            email_domain_parts = EMAIL_HOST.split('.')
            # Concatenate the 2nd to last and last items from the above split.
            # We assume that you all email is on a single domain.
            email_domain = email_domain_parts[-2] + '.' + email_domain_parts[-1]
            email_to = ['{0}@{1}'.format(site['modified_by'], email_domain)]
            utilities.send_email(email_message=message, email_subject=subject, email_to=email_to)

    if updates.get('status'):
        log.debug('Site update | ID - %s | Found status change', site['_id'])
        # If we are updating status, we will need to sync instances
        sync_instances = True
        if updates['status'] in ['installing', 'launching', 'locked', 'take_down', 'restore']:
            if updates['status'] == 'installing':
                log.debug('Site update | ID - %s | Status changed to installing')
                # Set new status on site record for update to settings files.
                site['status'] = 'installed'
                instance_operations.switch_settings_files(site)
                deploy_php_cache_clear = True
                patch_payload = '{"status": "installed"}'
            elif updates['status'] == 'launching':
                log.debug('Site update | ID - %s | Status changed to launching', site['_id'])
                site['status'] = 'launched'
                instance_operations.switch_settings_files(site)
                instance_operations.switch_web_root_symlinks(site)
                if site['path'] == 'homepage':
                    instance_operations.switch_homepage_files()
                deploy_drupal_cache_clear = True
                deploy_php_cache_clear = True
                # Set update group and status
                if site['path'] != 'homepage':
                    update_group = randint(0, 5)
                elif site['path'] == 'homepage':
                    update_group = 6
                patch_payload = {'status': 'launched', 'update_group': update_group}

                # Let fabric send patch since it is changing update group.
            elif updates['status'] == 'locked':
                log.debug('Site update | ID - %s | Status changed to locked', site['_id'])
                instance_operations.switch_settings_files(site)
                deploy_php_cache_clear = True
            elif updates['status'] == 'take_down':
                log.debug('Site update | ID - %s | Status changed to take_down', site['_id'])
                site['status'] = 'down'
                instance_operations.switch_settings_files(site)
                instance_operations.switch_web_root_symlinks(site)
                patch_payload = '{"status": "down"}'
                # Soft delete stats when we take down an instance.
                statistics_query = 'where={{"site":"{0}"}}'.format(site['_id'])
                statistics = utilities.get_eve('statistics', statistics_query)
                log.debug('Statistics | %s', statistics)
                if not statistics['_meta']['total'] == 0:
                    for statistic in statistics['_items']:
                        utilities.delete_eve('statistics', statistic['_id'])

            elif updates['status'] == 'restore':
                log.debug('Site update | ID - %s | Status changed to restore', site['_id'])
                site['status'] = 'installed'
                instance_operations.switch_settings_files(site)
                instance_operations.switch_web_root_symlinks(site)
                statistics_patch_payload = '{{"site": "{0}"}}'.format(site['_id'])
                statistics_patch = utilities.patch_eve(
                    'statistics', site['statistics'], statistics_patch_payload)
                deploy_update_database = True
                patch_payload = '{"status": "installed"}'
                deploy_drupal_cache_clear = True

            patch = utilities.patch_eve('sites', site['_id'], patch_payload)
            log.debug(patch)

    # Don't update settings files a second time if status is changing to 'locked'.
    if updates.get('settings'):
        log.info('Found settings change | %s', updates)
        # If we are updating the settings file, we will need to sync instances
        sync_instances = True
        if not updates.get('status') or updates['status'] != 'locked':
            instance_operations.switch_settings_files(site)
            deploy_php_cache_clear = True

    # We want to run these commands in this specific order.
    log.info('Site Update | Closing operations commands | Sync - %s | PHP Cache clear - %s | Drush rr - %s; updb - %s ; cc - %s', sync_instances, deploy_php_cache_clear, deploy_registry_rebuild, deploy_update_database, deploy_drupal_cache_clear)
    if sync_instances:
        instance_operations.sync_instances(site['sid'])
        execute(fabric_tasks.clear_php_cache)
    if deploy_php_cache_clear:
        execute(fabric_tasks.clear_php_cache)
    if deploy_registry_rebuild:
        execute(fabric_tasks.registry_rebuild, site=site)
    if deploy_update_database:
        execute(fabric_tasks.update_database, site=site)
    if deploy_drupal_cache_clear:
        execute(fabric_tasks.drush_cache_clear, sid=site['sid'])

    slack_text = 'Site Update - Success - {0}/sites/{1}'.format(API_URLS[ENVIRONMENT], site['_id'])
    slack_color = 'good'
    slack_link = '{0}/{1}'.format(BASE_URLS[ENVIRONMENT], site['path'])

    # Strip out fields that we don't care about.
    slack_updates = {k:updates[k] for k in updates if not k.startswith('_') and not k in ['modified_by', 'db_key', 'statistics']}

    slack_payload = {
        "text": slack_text,
        "attachments": [
            {
                "fallback": slack_text,
                "color": slack_color,
                "fields": [
                    {
                        "title": "Instance",
                        "value": slack_link,
                        "short": False
                    },
                    {
                        "title": "Environment",
                        "value": ENVIRONMENT,
                        "short": True
                    },
                    {
                        "title": "Update requested by",
                        "value": updates['modified_by'],
                        "short": True
                    },
                    {
                        "title": "Updates",
                        "value": str(json_util.dumps(slack_updates)),
                        "short": False
                    }
                ],
            }
        ],
    }
    utilities.post_to_slack_payload(slack_payload)


@celery.task
def site_remove(site):
    """
    Remove site from the server and delete Statistic item.

    :param site: Item to be removed.
    :return:
    """
    log.debug('Site remove | %s', site)
    # Check if stats object exists for the site first.
    statistics_query = 'where={{"site":"{0}"}}'.format(site['_id'])
    statistics = utilities.get_eve('statistics', statistics_query)
    log.debug('Statistics | %s', statistics)
    if not statistics['_meta']['total'] == 0:
        for statistic in statistics['_items']:
            utilities.delete_eve('statistics', statistic['_id'])

    try:
        log.debug('Site remove | Delete database')
        utilities.delete_database(site['sid'])
    except Exception as error:
        log.error('Site remove failed | Database remove failed | %s', error)
        # Want to keep trying to remove instances even if DB remove fails.
        pass

    instance_operations.instance_delete(site)
    instance_operations.sync_instances()
    execute(fabric_tasks.clear_php_cache)


@celery.task
def drush_prepare(drush_id, run=True):
    """
    Prepare to run the appropriate drush command and run it if desired

    :param drush_id: ID of drush command to run.
    :return:
    """
    log.debug('Drush | Prepare | Drush command - %s', drush_id)
    drush_command = utilities.get_single_eve('drush', drush_id)

    site_query = 'where={0}'.format(drush_command['query'])
    sites = utilities.get_eve('sites', site_query)
    log.debug('Drush | Prepare | Drush command - %s | Ran query - %s', drush_id, sites)
    if not sites['_meta']['total'] == 0 and run is True:
        batch_id = time.time()
        batch_count = 1
        batch_log = 'Batch started | ID - {0} | Batch size - {1}'.format(
            batch_id, str(sites['_meta']['total']))
        log.info(batch_log)
        for site in sites['_items']:
            batch_string = str(batch_count) + ' of ' + str(sites['_meta']['total'])
            drush_command_run.delay(
                site=site,
                command_list=drush_command['commands'],
                user=drush_command['modified_by'],
                batch_id=batch_id,
                batch_count=batch_string)
            batch_count += 1
        return batch_log
    else:
        return sites


@celery.task
def drush_command_run(site, command_list, user=None, batch_id=None, batch_count=None):
    """
    Run the appropriate command.

    :param site: A complete site item.
    :param command_list: List of commands to run.
    :param user: string Username that called the command.
    :return:
    """
    log.info('Batch ID - %s | Count - %s | Command - %s', batch_id, batch_count, command_list)
    log.debug('Batch ID - %s | Count - %s | Site - %s | Command - %s', batch_id, batch_count, site['sid'], command_list)

    if site['path'] != 'homepage':
        uri = BASE_URLS[ENVIRONMENT] + '/' + site['path']
    else:
        # Homepage
        uri = BASE_URLS[ENVIRONMENT]
    # Use List comprehension to add user prefix and URI suffix, then join the result.
    final_command = ' && '.join([command + ' --uri={0}'.format(uri) for command in command_list])
    log.debug('Batch ID - %s | Count - %s | Final Command - %s', batch_id, batch_count, final_command)

    start_time = time.time()

    fabric_task_result = execute(fabric_tasks.command_run_single, site=site,
                                 command=final_command, warn_only=True)

    command_time = time.time() - start_time
    log.info('Batch ID - %s | Count - %s | Command - %s | Time - %s | Result - %s',
             batch_id, batch_count, command_list, command_time, fabric_task_result)
    log.debug('Batch ID - %s | Count - %s | Site - %s | Command - %s | Time - %s | Result - %s',
             batch_id, batch_count, site['sid'], command_list, command_time, fabric_task_result)


@celery.task
def cron(status=None):
    """
    Prepare cron tasks and send them to subtasks.
    """
    log.info('Status - %s', status)
    # Build query.
    site_query_string = ['where={']
    log.debug('Prepare Cron | Found argument')
    if status:
        log.debug('Found status')
        site_query_string.append('"status":"{0}",'.format(status))
    else:
        log.debug('No status found')
        site_query_string.append('"status":{"$nin":["take_down","down","restore"]},')

    site_query = ''.join(site_query_string)
    log.debug('Query after join -| %s', site_query)
    # Remove trailing comma.
    site_query = site_query.rstrip('\,')
    log.debug('Query after rstrip | %s', site_query)
    # Add closing brace.
    site_query += '}'
    log.debug('Query final | %s', site_query)

    sites = utilities.get_eve('sites', site_query)
    if not sites['_meta']['total'] == 0:
        for site in sites['_items']:
            cron_run.delay(site)


@celery.task
def cron_run(site):
    """
    Run cron

    :param site: A complete site item.
    :return:
    """
    log.info('Site - %s | %s', site['sid'], site)
    start_time = time.time()

    if site['path'] != 'homepage':
        uri = BASE_URLS[ENVIRONMENT] + '/' + site['path']
    else:
        uri = BASE_URLS[ENVIRONMENT]
    log.debug('Site - %s | uri - %s', site['sid'], uri)
    command = 'drush elysia-cron run --uri={1}'.format(WEBSERVER_USER, uri)
    try:
        execute(fabric_tasks.command_run_single, site=site, command=command)
        instance_operations.correct_fs_permissions(site)
    except CronException as error:
        log.error('Site - %s | Cron failed | Error - %s', site['sid'], error)
        raise

    command_time = time.time() - start_time
    log.info('Site - %s | Cron success | Time - %s', site['sid'], command_time)


@celery.task
def available_sites_check():
    """
    Check to see how many instances we have ready to be handed out and add some more if needed.
    """
    site_query = 'where={"status":{"$in":["pending","available"]}}'
    sites = utilities.get_eve('sites', site_query)
    actual_site_count = sites['_meta']['total']
    if actual_site_count < DESIRED_SITE_COUNT:
        needed_sites_count = DESIRED_SITE_COUNT - actual_site_count
        while needed_sites_count > 0:
            payload = {
                "status": "pending",
            }
            utilities.post_eve('sites', payload)
            needed_sites_count -= 1


@celery.task
def delete_stuck_pending_sites():
    """
    Task to delete pending sites that don't provision correctly for some reason.
    """
    site_query = 'where={"status":"pending"}'
    sites = utilities.get_eve('sites', site_query)
    log.debug('Sites - %s', sites)
    # Loop through and remove sites that are more than 15 minutes old.
    if not sites['_meta']['total'] == 0:
        for site in sites['_items']:
            # Parse date string into structured datetime.
            # See https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior
            # for mask format.
            date_created = datetime.strptime(site['_created'], "%Y-%m-%d %H:%M:%S %Z")
            # Get datetime now and calculate the age of the site. Since our timestamp is in GMT, we
            # need to use UTC.
            time_since_creation = datetime.utcnow() - date_created
            log.debug('%s has timedelta of %s. Created: %s Current: %s',
                      site['sid'], time_since_creation, date_created, datetime.utcnow())
            if time_since_creation > timedelta(minutes=20):
                utilities.delete_eve('sites', site['_id'])


@celery.task
def delete_all_available_sites():
    """
    Get a list of available sites and delete them.
    """
    site_query = 'where={"status":"available"}'
    sites = utilities.get_eve('sites', site_query)
    log.debug('Sites - %s', sites)
    if not sites['_meta']['total'] == 0:
        for site in sites['_items']:
            log.debug('Site - %s', site)
            utilities.delete_eve('sites', site['_id'])


@celery.task
def remove_unused_code():
    """
    If a code item is more than 90 days old, not current, and unused then remove it.
    """
    time_ago = datetime.utcnow() - timedelta(days=90)
    code_query = 'where={{"meta.is_current":false,"_created":{{"$lte":"{0}"}}}}'.format(
        time_ago.strftime("%Y-%m-%d %H:%M:%S GMT"))
    code_items = utilities.get_eve('code', code_query)

    for code in code_items['_items']:
        # Check for sites using this piece of code.
        if code['meta']['code_type'] in ['module', 'theme', 'library']:
            code_type = 'package'
        else:
            code_type = code['meta']['code_type']
        log.debug('code - %s | code_type - %s', code['_id'], code_type)
        site_query = 'where={{"code.{0}":"{1}"}}'.format(code_type, code['_id'])
        sites = utilities.get_eve('sites', site_query)
        log.debug('Delete | code - %s | sites result - %s', code['_id'], sites)
        if sites['_meta']['total'] == 0:
            log.info('Removing unused item | code - %s', code['_id'])
            utilities.delete_eve('code', code['_id'])


@celery.task
def remove_orphan_statistics():
    """
    Get a list of statistics and key them against a list of active instances.
    """
    sites = utilities.get_eve('sites')
    statistics = utilities.get_eve('statistics')
    log.debug('Statistics | %s', statistics)
    log.debug('Sites | %s', sites)
    site_id_list = []
    # Make as list of ids for easy checking.
    if not statistics['_meta']['total'] == 0:
        if not sites['_meta']['total'] == 0:
            for site in sites['_items']:
                site_id_list.append(site['_id'])
                log.debug('Sites list | %s', site_id_list)
        for statistic in statistics['_items']:
            if statistic['site'] not in site_id_list:
                log.info('Statistic not in list | %s', statistic['_id'])
                utilities.delete_eve('statistics', statistic['_id'])


@celery.task
def take_down_installed_old_sites():
    """
    In non-prod environments, take down instances that are older than 35 days.
    """
    if ENVIRONMENT in ['dev', 'test']:
        site_query = 'where={"status":"installed"}'
        sites = utilities.get_eve('sites', site_query)
        # Loop through and remove sites that are more than 35 days old.
        for site in sites['_items']:
            # Parse date string into structured time.
            # See https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior
            # for mask format.
            date_created = time.strptime(site['_created'], "%Y-%m-%d %H:%M:%S %Z")
            # Get time now, Convert date_created to seconds from epoch and calculate the age of the
            # site.
            seconds_since_creation = time.time() - time.mktime(date_created)
            log.info('Take down old instances | %s is %s seconds old. Created: %s Current: %s',
                     site['sid'], seconds_since_creation, time.mktime(date_created), time.time())
            # 35 days * 24 hrs * 60 min * 60 sec = 302400 seconds
            if seconds_since_creation > 3024000:
                # Patch the status to 'take_down'.
                payload = {'status': 'take_down'}
                utilities.patch_eve('sites', site['_id'], payload)


@celery.task
def verify_statistics():
    """
    Get a list of statistics items that have not been updated in 36 hours and notify users.
    """
    time_ago = datetime.utcnow() - timedelta(hours=36)
    statistics_query = 'where={{"_updated":{{"$lte":"{0}"}}}}'.format(
        time_ago.strftime("%Y-%m-%d %H:%M:%S GMT"))
    outdated_statistics = utilities.get_eve('statistics', statistics_query)
    log.debug('Old statistics time - %s', time_ago.strftime("%Y-%m-%d %H:%M:%S GMT"))
    log.debug('outdated_statistics items - %s', outdated_statistics)
    statistic_id_list = []
    if not outdated_statistics['_meta']['total'] == 0:
        for outdated_statistic in outdated_statistics['_items']:
            statistic_id_list.append(outdated_statistic['_id'])

        log.debug('statistic_id_list | %s', statistic_id_list)

        site_query = 'where={{"statistics":{{"$in":{0}}}}}'.format(json.dumps(statistic_id_list))
        log.debug('Site query | %s', site_query)
        sites = utilities.get_eve('sites', site_query)
        sites_id_list = []
        if not sites['_meta']['total'] == 0:
            log.info('More than 0 sites')
            for site in sites['_items']:
                sites_id_list.append(site['sid'])

            log.info('sites_id_list | %s', str(sites_id_list))

            slack_fallback = '{0} statistics items have not been updated in 36 hours.'.format(
                    len(statistic_id_list))
            slack_link = '{0}/statistics?{1}'.format(BASE_URLS[ENVIRONMENT], site_query)
            slack_payload = {
                "text": 'Outdated Statistics',
                "attachments": [
                    {
                        "fallback": slack_fallback,
                        "color": 'danger',
                        "title": 'Some statistics items have not been updated in 36 hours.',
                        "fields": [
                            {
                                "title": "Count",
                                "value": len(statistic_id_list),
                                "short": True
                            },
                            {
                                "title": "Environment",
                                "value": ENVIRONMENT,
                                "short": True
                            },
                        ],
                    },
                    {
                        "fallback": 'Site list',
                        # A lighter red.
                        "color": '#ee9999',
                        "fields": [
                            {
                                "title": "Site list",
                                "value": json.dumps(sites_id_list),
                                "short": False,
                                "title_link": slack_link
                            }
                        ]
                    }
                ],
            }

            utilities.post_to_slack_payload(slack_payload)


@celery.task(time_limit=1200)
def backup_instances_all(backup_type='routine'):
    """Backup all instance EXCEPT for the ones that we know are too large, currently `today` and
    `cwa`

    20 minute time limit

    Keyword Arguments:
        backup_type {str} -- 'routine', 'update', or 'on_demand' (default: {'routine'})
    """
    log.info('Backup all instances')
    # Get the instance IDs for excluded paths
    exclude_instances = utilities.get_eve(
        'sites', 'where={{"path":{{"$in":{0}}}}}'.format(json.dumps(BACKUPS_LARGE_INSTANCES)))
    log.debug('Backup all instances | Exclude instances - %s', exclude_instances['_items'])
    exclude_ids = []
    for instance in exclude_instances['_items']:
        exclude_ids.append(instance['_id'])
    log.debug('Backup all instances | List of IDs to exclude - %s', exclude_ids)
    # TODO: Max results
    statistics_query = 'where={{"status":{{"$in":["installed","launched"]}},"days_since_last_edit":0,"site":{{"$nin":{0}}}}}'.format(
        json.dumps(exclude_ids))
    log.debug('Backup all instances | Stats query - %s', statistics_query)
    statistics = utilities.get_eve(
        'statistics', statistics_query)
    batch_id = time.time()
    if not statistics['_meta']['total'] == 0:
        for statistic in statistics['_items']:
            site = utilities.get_single_eve('sites', statistic['site'])
            backup_create.delay(site=site, backup_type=backup_type, batch=batch_id)
    # Report to slack
    log.info('Atlas operational statistic | Batch - %s | Type - %s | Count - %s',
             batch_id, backup_type, statistics['_meta']['total'])

    slack_fallback = '{0} {1} backups started'.format(statistics['_meta']['total'], backup_type)
    slack_color = 'good'
    slack_payload = {
        "text": 'Backups started',
        "attachments": [
            {
                "fallback": slack_fallback,
                "color": slack_color,
                "fields": [
                    {"title": "Environment", "value": ENVIRONMENT, "short": True},
                    {"title": "Backup Type", "value": backup_type, "short": True},
                    {"title": "Count", "value": statistics['_meta']['total'], "short": True}
                ],
            }
        ],
    }
    utilities.post_to_slack_payload(slack_payload)


@celery.task(time_limit=2100)
def backup_instances_large(backup_type='routine'):
    """Backup known large instances, currently `today` and `cwa`

    35 minute time limit

    Keyword Arguments:
        backup_type {str} -- 'routine', 'update', or 'on_demand' (default: {'routine'})
    """
    log.info('Backup large instances')
    # Get the instance IDs for include paths
    instances = utilities.get_eve('sites', 'where={{"path":{{"$in":[{0}]}}}}'.format(
        json.dumps(BACKUPS_LARGE_INSTANCES)))
    log.debug('Backup large instances | Include instances - %s', instances['_items'])
    instances_ids = []
    for instance in instances_instances['_items']:
        instances_ids.append(instance['_id'])
    log.debug('Backup large instances | List of IDs to include - %s', instances_ids)
    statistics_query = 'where={{"status":{{"$in":["installed","launched"]}},"days_since_last_edit":{{"$lte":7}},"site":{{"$in":[{0}]}}}}'.format(
        json.dumps(instances_ids))
    log.debug('Backup large instances | Stats query - %s', statistics_query)
    statistics = utilities.get_eve(
        'statistics', statistics_query)
    batch_id = time.time()
    if not statistics['_meta']['total'] == 0:
        for statistic in statistics['_items']:
            site = utilities.get_single_eve('sites', statistic['site'])
            backup_create.delay(site=site, backup_type=backup_type, batch=batch_id)
    # Report to slack
    log.info('Atlas operational statistic | Batch - %s | Type - %s | Count - %s',
             batch_id, backup_type, statistics['_meta']['total'])

    slack_fallback = '{0} {1} backups started'.format(statistics['_meta']['total'], backup_type)
    slack_color = 'good'
    slack_payload = {
        "text": 'Backups started',
        "attachments": [
            {
                "fallback": slack_fallback,
                "color": slack_color,
                "fields": [
                    {"title": "Environment", "value": ENVIRONMENT, "short": True},
                    {"title": "Backup Type", "value": backup_type, "short": True},
                    {"title": "Count", "value": statistics['_meta']['total'], "short": True}
                ],
            }
        ],
    }
    utilities.post_to_slack_payload(slack_payload)


@celery.task
def backup_create(site, backup_type, batch=None):
    log.debug('Backup | Create | Batch - %s | Site - %s', batch, site)
    log.info('Backup | Create | Batch - %s | Site - %s', batch, site['_id'])
    execute(fabric_tasks.backup_create, site=site, backup_type=backup_type)
    log.info('Backup | Create | Batch - %s | Site - %s | Backup finished', batch, site['_id'])


@celery.task
def backup_restore(backup_record, original_instance, package_list):
    log.info('Backup | Restore | Backup ID - %s', backup_record['_id'])
    log.debug('Backup | Restore | Backup Recorsd - %s | Original instance - %s | Package List - %s',
              backup_record, original_instance, package_list)
    execute(fabric_tasks.backup_restore, backup_record=backup_record,
            original_instance=original_instance, package_list=package_list)


@celery.task
def backup_remove(item):
    log.debug('Backup | Delete | Item - %s', item)
    log.info('Backup | Delete | Item ID - %s', item['_id'])
    backup_operations.backup_delete(item)
    log.info('Backup | Delete | Item - %s | Delete finished', item['_id'])


@celery.task
def remove_old_backups():
    """
    Delete backups older than 90 days unless it is the only backup.
    """
    time_ago = datetime.utcnow() - timedelta(days=90)
    backup_query = 'where={{"_created":{{"$lte":"{0}"}}}}'.format(
        time_ago.strftime("%Y-%m-%d %H:%M:%S GMT"))
    backups = utilities.get_eve('backup', backup_query)
    # Loop through and remove backups that are old.
    if not backups['_meta']['total'] == 0:
        for backup in backups['_items']:
            check_for_other = utilities.get_eve(
                'backup', 'where={{"site":"{0}"}}'.format(backup['site']))
            if not check_for_other['_meta']['total'] == 1:
                log.info('Delete old backup | backup - %s', backup)
                utilities.delete_eve('backup', backup['_id'])
            else:
                log.info('Backups | Will not remove old backup, it is the only one | Backup - %s | Site %s',
                         backup['_id'], backup['site'])


@celery.task
def remove_extra_backups():
    """
    Delete extra backups, we only want to keep 5 per instance.
    """
    backup_data = utilities.get_eve('backup')
    log.debug('Delete extra backups | backup_data - %s', backup_data)
    instance_ids = []
    for item in backup_data['_items']:
        instance_ids.append(item['site'])
    log.debug('Delete extra backups | Instance list - %s', instance_ids)
    counts = Counter(instance_ids)
    log.info('Delete extra backups | counts - %s', counts)
    # Sort out the list for values greater than 5
    high_count = {k: v for (k, v) in counts.items() if v > 5}
    log.info('Delete extra backups | High Count - %s', high_count)
    if high_count:
        for item in high_count:
            # Get a list of backups for this instance, sorted by age (oldest first)
            instance_backup_query = 'where={{"site":"{0}"}}&sort=[("_created",1)]'.format(item)
            instance_backups = utilities.get_eve('backup', instance_backup_query)
            log.info('Delete extra backups | List of backups - %s', instance_backups)
            # Remove the oldest
            backup_count = instance_backups['_meta']['total']
            for back_to_remove in instance_backups['_items']:
                if backup_count > 5:
                    log.info('Delete extra backups | Backup count - %s', backup_count)
                    log.info('Delete extra backup | Backup to remove - %s', back_to_remove['_id'])
                    utilities.delete_eve('backup', back_to_remove['_id'])
                    backup_count -= 1


@celery.task
def remove_failed_backups():
    """
    Delete failed backups.
    """
    # Get all backups
    time_ago = datetime.utcnow() - timedelta(minutes=90)
    backup_query = 'where={{"state":"pending","_created":{{"$lte":"{0}"}}}}'.format(
        time_ago.strftime("%Y-%m-%d %H:%M:%S GMT"))
    backups = utilities.get_eve('backup', backup_query)
    for item in backups['_items']:
        utilities.delete_eve('backup', item['_id'])


@celery.task
def report_routine_backups():
    """
    Report count of complete routine backups in the last 24 hours.
    """
    time_ago = datetime.utcnow() - timedelta(hours=24)
    query = 'where={{"state":"complete","backup_type":"routine","_created":{{"$gte":"{0}"}}}}'.format(
        time_ago.strftime("%Y-%m-%d %H:%M:%S GMT"))
    backups = utilities.get_eve('backup', query)
    log.info('Atlas operational statistic | Complete routine backups in last 24 hours - %s',
             backups['_meta']['total'])

    slack_fallback = '{0} complete routine backups in last 24 hours'.format(
        backups['_meta']['total'])
    slack_color = 'good'
    slack_payload = {
        "text": 'Report - Routine backups in last 24 hours.',
        "attachments": [
            {
                "fallback": slack_fallback,
                "color": slack_color,
                "fields": [
                    {
                        "title": "Environment",
                        "value": ENVIRONMENT,
                        "short": True
                    },
                    {
                        "title": "Complete routine backups",
                        "value": backups['_meta']['total'],
                        "short": False
                    }
                ],
            }
        ],
    }
    utilities.post_to_slack_payload(slack_payload)


@celery.task
def clear_php_cache():
    """
    Celery task to clear PHP cache on all webservers.
    """
    log.info('Clear PHP cache')
    execute(fabric_tasks.clear_php_cache)


@celery.task
def import_code(env):
    """
    Import code definitions from another Atlas instance.

    :param env: Environment to target get code list from
    """
    target_url = '{0}/code'.format(API_URLS[env])
    r = requests.get(target_url, verify=SSL_VERIFICATION)
    if r.ok:
        data = r.json()
        log.debug('Import Code | Target data | %s', data)

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
            utilities.post_eve('code', payload)


@celery.task
def rebalance_update_groups():
    """
    Redistribute instances into update groups.
    :return:
    """
    log.info
    installed_query = 'where={"status":"installed"}'
    installed_sites = utilities.get_eve('sites', installed_query)
    launched_query = 'where={"status":"launched"}'
    launched_sites = utilities.get_eve('sites', launched_query)
    installed_update_group = 0
    launched_update_group = 0
    if not installed_sites['_meta']['total'] == 0:
        for site in installed_sites['_items']:
            patch_payload = '{{"update_group": {0}}}'.format(installed_update_group)
            if installed_update_group < 2:
                installed_update_group += 1
            else:
                installed_update_group = 0
            utilities.patch_eve('sites', site['_id'], patch_payload)

    if not launched_sites['_meta']['total'] == 0:
        for site in launched_sites['_items']:
            # Only update if the group is less than 6.
            if site['update_group'] < 6:
                patch_payload = '{{"update_group": {0}}}'.format(launched_update_group)
                if launched_update_group < 5:
                    launched_update_group += 1
                else:
                    launched_update_group = 0
                utilities.patch_eve('sites', site['_id'], patch_payload)


@celery.task
def update_settings_file(site, batch_id, count, total):
    log.info('Command | Update Settings file | Batch - %s | %s of %s | Instance - %s',
             batch_id, count, total, site)
    try:
        instance_operations.switch_settings_files(site)
        log.info('Command | Update Settings file | Batch - %s | %s of %s | Instance - %s | Complete',
                 batch_id, count, total, site)
    except Exception as error:
        log.error('Command | Update Settings file | Batch - %s | %s of %s | Instance - %s | Error - %s',
                  batch_id, count, total, site, error)
        raise
    instance_operations.sync_instances(site['sid'])
    execute(fabric_tasks.clear_php_cache)


@celery.task
def update_homepage_files():
    log.info('Command | Update Homepage files')
    try:
        instance_operations.switch_homepage_files()
        log.info('Command | Update Homepage files | Complete')
    except Exception as error:
        log.error('Command | Update Homepage files | Error - %s', error)
        raise
    instance_operations.sync_web_root()


@celery.task
def instance_heal(instances):
    """
    Verify instance is correctly deployed.
    """
    log.info('Heal | Instances')
    log.debug('Heal | Instances | Item - %s', instances)
    # Setup a chord. Takes a 'group' (list of tasks that should be applied in parallel) and executes
    # another task after the group is complete.
    # In the second task, using .si creates an immutable signature so the return value of the
    # previous tasks will be ignored.
    task_group = chord((_instance_heal.s(instance) for instance in instances['_items']), instance_sync.si())()


@celery.task
def _instance_heal(instance):
    """
    Sub task for instance_heal. Perform actual heal operations
    """
    log.info('Heal | Instance | Instance - %s', instance['_id'])
    log.debug('Heal | Instance | Instance - %s', instance)
    # We are not removing the DB or user uploaded files during heal.
    instance_operations.instance_delete(instance, nfs_preserve=True)
    instance_operations.instance_create(instance, nfs_preserve=True)


@celery.task
def instance_sync():
    """
    Sub task for instance_heal. Sync healed instances to server
    """
    # Update homepage files.
    instance_operations.switch_homepage_files()
    instance_operations.sync_instances()
    execute(fabric_tasks.clear_php_cache)


@celery.task
def correct_file_permissions(instance):
    """
    Verify code is correctly deployed.
    """
    log.info('Correct file permissions | Instance - %s', instance)
    try:
        instance_operations.correct_fs_permissions(instance)
    except Exception as error:
        log.error('Correct file permissions | Instance - %s | Error', instance['sid'], error)
        raise


@celery.task(time_limit=2000)
def import_backup(env, backup_id, target_instance):
    """Download and import a backup

    Arguments:
        env {[type]} -- [description]
        backup_id {[type]} -- [description]
        target_instance {[type]} -- [description]
    """

    log.info('Import Backup | Source ENV - %s | Source Backup ID - %s', env, backup_id)
    backup = requests.get(
        '{0}/backup/{1}'.format(API_URLS[env], backup_id), verify=SSL_VERIFICATION)
    log.info('Import Backup | Backup - %s', backup)

    target = utilities.get_single_eve('sites', target_instance)
    utilities.create_database(target['sid'], target['db_key'])
    instance_operations.instance_delete(target)
    instance_operations.instance_create(target)
    instance_operations.sync_instances()
    execute(fabric_tasks.import_backup, backup=backup.json(),
            target_instance=target, source_env=env)
    instance_operations.correct_fs_permissions(target)


@celery.task
def saml_create():
    try:
        log.debug('Create SAML database')
        utilities.create_saml_database()
    except Exception as error:
        log.error('SAML Database creation failed | %s', error)
        raise


@celery.task
def saml_delete():
    try:
        log.debug('Delete SAML database')
        utilities.delete_saml_database()
    except Exception as error:
        log.error('SAML Database deletion failed | %s', error)
        raise
