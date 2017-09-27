"""
    atlas.tasks
    ~~~~~~
    Celery tasks for Atlas.
"""
import logging
import time
import json

from datetime import datetime, timedelta
from celery import Celery
from fabric.api import execute

from atlas import fabric_tasks
from atlas import utilities
from atlas import config_celery
from atlas.config import (ENVIRONMENT, WEBSERVER_USER, DESIRED_SITE_COUNT)
from atlas.config_servers import (BASE_URLS, API_URLS)

# Setup a sub-logger
# Best practice is to setup sub-loggers rather than passing the main logger between different parts of the application.
# https://docs.python.org/3/library/logging.html#logging.getLogger and
# https://stackoverflow.com/questions/39863718/how-can-i-log-outside-of-main-flask-module
log = logging.getLogger('atlas.tasks')

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
        command = 'sudo -u {0} drush elysia-cron run'.format(WEBSERVER_USER)
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
                "username": 'Atlas',
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
    code_deploy_fabric_task_result = execute(fabric_tasks.code_deploy, item=item)
    log.debug('Code Deploy | Deploy Error | %s', code_deploy_fabric_task_result)

    # The fabric_result is a dict of {hosts: result} from fabric.
    # We loop through each row and add it to a new dict if value is not
    # None.
    # This uses constructor syntax https://doughellmann.com/blog/2012/11/12/the-performance-impact-of-using-dict-instead-of-in-cpython-2-7-2/.
    errors = {k: v for k, v in code_deploy_fabric_task_result.iteritems() if v is not None}

    if errors:
        text = 'Error'
        slack_color = 'danger'
    else:
        text = 'Success'
        slack_color = 'good'

    slack_fallback = '{0} - {1}'.format(item['meta']['name'], item['meta']['version'])

    slack_payload = {

        "text": 'Code Deploy',
        "username": 'Atlas',
        "attachments": [
            {
                "fallback": slack_fallback,
                "color": slack_color,
                "author_name": item['created_by'],
                "title": text,
                "fields": [
                    {
                        "title": "Name",
                        "value": item['meta']['name'],
                        "short": True
                    },
                    {
                        "title": "Environment",
                        "value": ENVIRONMENT,
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

    if errors:
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


@celery.task
def code_update(updated_item, original_item):
    """
    Update code checkout.

    :param updated_item:
    :param original_item:
    :return:
    """
    log.debug('Code update | %s', updated_item)
    fab_task = execute(fabric_tasks.code_update, updated_item=updated_item,
                       original_item=original_item)

    name = updated_item['meta']['name'] if updated_item['meta']['name'] else original_item['meta']['name']
    version = updated_item['meta']['version'] if updated_item['meta']['version'] else original_item['meta']['version']

    if False not in fab_task.values():
        slack_title = 'Code Update - Success'
        slack_color = 'good'
        code_string = '{0} - {1}'.format(name, version)

        slack_payload = {
            "text": slack_title,
            "username": 'Atlas',
            "attachments": [
                {
                    "fallback": slack_title,
                    "color": slack_color,
                    "title": slack_title,
                    "fields": [
                        {
                            "title": "Code",
                            "value": code_string,
                            "short": True
                        },
                        {
                            "title": "Environment",
                            "value": ENVIRONMENT,
                            "short": True
                        },
                    ],
                }
            ],
        }
        utilities.post_to_slack_payload(slack_payload)


@celery.task
def code_remove(item):
    """
    Remove code from the server.

    :param item: Item to be removed.
    :return:
    """
    log.debug('Code remove | %s', item)
    fab_task = execute(fabric_tasks.code_remove, item=item)

    if False not in fab_task.values():
        # Slack notification
        slack_title = 'Code Remove - Success'
        slack_color = 'good'
        code_string = '{0} - {1}'.format(item['meta']['name'], item['meta']['version'])

        slack_payload = {
            "text": slack_title,
            "username": 'Atlas',
            "attachments": [
                {
                    "fallback": slack_title,
                    "color": slack_color,
                    "title": slack_title,
                    "fields": [
                        {
                            "title": "Code",
                            "value": code_string,
                            "short": True
                        },
                        {
                            "title": "Environment",
                            "value": ENVIRONMENT,
                            "short": True
                        },
                    ],
                }
            ],
        }
        utilities.post_to_slack_payload(slack_payload)


@celery.task
def site_provision(site):
    """
    Provision a new instance with the given parameters.

    :param site: A single site.
    :return:
    """
    log.debug('Site provision | %s', site)
    start_time = time.time()
    # 'db_key' needs to be added here and not in Eve so that the encryption
    # works properly.
    site['db_key'] = utilities.encrypt_string(utilities.mysql_password())
    # Set future site status for settings file creation.
    site['status'] = 'available'

    try:
        log.debug('Site provision | Create database')
        utilities.create_database(site['sid'], site['db_key'])
    except Exception as error:
        log.error('Site provision failed | Database creation failed | %s', error)
        raise

    try:
        execute(fabric_tasks.site_provision, site=site)
    except Exception as error:
        log.error('Site provision failed | Error Message | %s', error)
        raise

    try:
        execute(fabric_tasks.site_install, site=site)
    except Exception as error:
        log.error('Site install failed | Error Message | %s', error)
        raise

    patch_payload = {'status': 'available',
                     'db_key': site['db_key'],
                     'statistics': site['statistics']}
    patch = utilities.patch_eve('sites', site['_id'], patch_payload)

    profile = utilities.get_single_eve('code', site['code']['profile'])
    profile_string = profile['meta']['name'] + '-' + profile['meta']['version']

    core = utilities.get_single_eve('code', site['code']['core'])
    core_string = core['meta']['name'] + '-' + core['meta']['version']

    provision_time = time.time() - start_time
    log.info('Atlas operational statistic | Site Provision | %s | %s | %s ',
             core_string, profile_string, provision_time)
    log.debug('Site provision | Patch | %s', patch)

    # Slack notification
    slack_title = 'Site provision - Success'
    slack_text = 'Site provision - Success - {0}/{1}'.format(BASE_URLS[ENVIRONMENT], site['path'])
    slack_color = 'good'
    slack_link = '{0}/{1}'.format(BASE_URLS[ENVIRONMENT], site['path'])

    slack_payload = {
        "text": slack_text,
        "username": 'Atlas',
        "attachments": [
            {
                "fallback": slack_text,
                "color": slack_color,
                "title": slack_title,
                "fields": [
                    {
                        "title": "Instance",
                        "value": slack_link,
                        "short": True
                    },
                    {
                        "title": "Time",
                        "value": provision_time + ' sec',
                        "short": True
                    },
                    {
                        "title": "Environment",
                        "value": ENVIRONMENT,
                        "short": True
                    },
                ],
            }
        ],
    }
    utilities.post_to_slack_payload(slack_payload)

    # Logstash statistics
    logstash_payload = {'provision_time': provision_time, 'logsource': 'atlas'}
    utilities.post_to_logstash_payload(payload=logstash_payload)


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

    if updates.get('code'):
        log.debug('Site update | ID - %s | Found code changes', site['_id'])
        core_change = False
        profile_change = False
        package_change = False
        if 'core' in updates['code']:
            log.debug('Site update | ID - %s | Found core change', site['_id'])
            core_change = True
            execute(fabric_tasks.site_core_update, site=site)
        if 'profile' in updates['code']:
            log.debug('Site update | ID - %s | Found profile change', site['_id'])
            profile_change = True
            execute(fabric_tasks.site_profile_update, site=site, original=original, updates=updates)
        if 'package' in updates['code']:
            log.debug('Site update | ID - %s | Found package changes', site['_id'])
            package_change = True
            execute(fabric_tasks.site_package_update, site=site)
        if core_change or profile_change or package_change:
            execute(fabric_tasks.registry_rebuild, site=site)
            execute(fabric_tasks.update_database, site=site)
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
            email_to = ['{0}@colorado.edu'.format(site['modified_by'])]
            utilities.send_email(email_message=message, email_subject=subject, email_to=email_to)

    if updates.get('status'):
        log.debug('Site update | ID - %s | Found status change', site['_id'])
        if updates['status'] in ['installing', 'launching', 'locked', 'take_down', 'restore']:
            if updates['status'] == 'installing':
                log.debug('Site update | ID - %s | Status changed to installing')
                # Set new status on site record for update to settings files.
                site['status'] = 'installed'
                execute(fabric_tasks.update_settings_file, site=site)
                execute(fabric_tasks.clear_apc)
                patch_payload = '{"status": "installed"}'
            elif updates['status'] == 'launching':
                log.debug('Site update | ID - %s | Status changed to launching', site['_id'])
                site['status'] = 'launched'
                execute(fabric_tasks.update_settings_file, site=site)
                execute(fabric_tasks.site_launch, site=site)
                if ENVIRONMENT is not 'local':
                    execute(fabric_tasks.update_f5)
                # Let fabric send patch since it is changing update group.
            elif updates['status'] == 'locked':
                log.debug('Site update | ID - %s | Status changed to locked', site['_id'])
                execute(fabric_tasks.update_settings_file, site=site)
            elif updates['status'] == 'take_down':
                log.debug('Site update | ID - %s | Status changed to take_down', site['_id'])
                site['status'] = 'down'
                execute(fabric_tasks.update_settings_file, site=site)
                # execute(fabric_tasks.site_backup, site=site)
                execute(fabric_tasks.site_take_down, site=site)
                patch_payload = '{"status": "down"}'
            elif updates['status'] == 'restore':
                log.debug('Site update | ID - %s | Status changed to restore', site['_id'])
                site['status'] = 'installed'
                execute(fabric_tasks.update_settings_file, site=site)
                execute(fabric_tasks.site_restore, site=site)
                execute(fabric_tasks.update_database, site=site)
                patch_payload = '{"status": "installed"}'

            if updates['status'] != 'launching':
                patch = utilities.patch_eve('sites', site['_id'], patch_payload)
                log.debug(patch)

    # Don't update settings files a second time if status is changing to 'locked'.
    if updates.get('settings'):
        if not updates.get('status') or updates['status'] != 'locked':
            log.debug('Found settings change.')
            if updates['settings'].get('page_cache_maximum_age') != original['settings'].get('page_cache_maximum_age'):
                log.debug('Found page_cache_maximum_age change.')
            execute(fabric_tasks.update_settings_file, site=site)

    slack_title = 'Site Update - Success'
    slack_text = 'Site Update - Success - {0}/{1}'.format(BASE_URLS[ENVIRONMENT], site['path'])
    slack_color = 'good'
    slack_link = '{0}/{1}'.format(BASE_URLS[ENVIRONMENT], site['path'])

    slack_payload = {
        "text": slack_text,
        "username": 'Atlas',
        "attachments": [
            {
                "fallback": slack_text,
                "color": slack_color,
                "author_name": updates['modified_by'],
                "title": slack_title,
                "fields": [
                    {
                        "title": "Instance",
                        "value": slack_link,
                        "short": True
                    },
                    {
                        "title": "Environment",
                        "value": ENVIRONMENT,
                        "short": True
                    },
                ],
            }
        ],
        "user": updates['modified_by']
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
    if site['type'] == 'express':
        # execute(fabric_tasks.site_backup, site=site)
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

        execute(fabric_tasks.site_remove, site=site)

    if ENVIRONMENT != 'local' and site['type'] == 'legacy':
        execute(fabric_tasks.update_f5)

    slack_title = '{0}/{1}'.format(BASE_URLS[ENVIRONMENT], site['path'])
    slack_text = 'Site Remove - Success - {0}/{1}'.format(BASE_URLS[ENVIRONMENT], site['path'])
    slack_color = 'good'
    slack_link = '{0}/{1}'.format(BASE_URLS[ENVIRONMENT], site['path'])

    slack_payload = {
        "text": slack_text,
        "username": 'Atlas',
        "attachments": [
            {
                "fallback": slack_text,
                "color": slack_color,
                "author_name": site['modified_by'],
                "title": slack_title,
                "fields": [
                    {
                        "title": "Instance",
                        "value": slack_link,
                        "short": True
                    },
                    {
                        "title": "Environment",
                        "value": ENVIRONMENT,
                        "short": True
                    },
                ],
            }
        ],
        "user": site['modified_by']
    }
    utilities.post_to_slack_payload(slack_payload)


@celery.task
def command_prepare(item):
    """
    Prepare sites to run the appropriate command.

    :param item: A complete command item, including new values.
    :return:
    """
    log.debug('Prepare Command | Item - %s', item)
    if item['command'] == 'clear_apc':
        execute(fabric_tasks.clear_apc)
        return
    if item['command'] == 'import_code':
        utilities.import_code(item['query'])
        return
    if item['command'] == 'rebalance_update_groups':
        utilities.rebalance_update_groups(item)
        return
    if item['query']:
        site_query = 'where={0}'.format(item['query'])
        sites = utilities.get_eve('sites', site_query)
        log.debug('Prepare Command | Item - %s | Ran query - %s', item['_id'], sites)
        if not sites['_meta']['total'] == 0:
            for site in sites['_items']:
                if item['command'] == 'update_settings_file':
                    log.debug('Prepare Command | Item - %s | Update Settings file | Instance - %s', item['_id'], site['_id'])
                    command_wrapper.delay(execute(fabric_tasks.update_settings_file, site=site))
                    continue
                if item['command'] == 'update_homepage_extra_files':
                    log.debug('Prepare Command | Item - %s | Update Homepage Extra files | Instance - %s', item['_id'], site['_id'])
                    command_wrapper.delay(execute(fabric_tasks.update_homepage_extra_files))
                    continue
                command_run.delay(site=site,
                                  command=item['command'],
                                  single_server=item['single_server'],
                                  user=item['modified_by'])
            # After all the commands run, flush APC.
            if item['command'] == 'update_settings_file':
                log.debug('Prepare Command | Item - %s | Clear APC', item['_id'])
                command_wrapper.delay(execute(fabric_tasks.clear_apc))


@celery.task
def command_wrapper(fabric_command):
    """
    Wrapper to run specific commands as delegate tasks.
    :param fabric_command: Fabric command to call
    :return:
    """
    log.debug('Command wrapper | %s', fabric_command)
    return fabric_command


@celery.task
def command_run(site, command, single_server, user=None):
    """
    Run the appropriate command.

    :param site: A complete site item.
    :param command: Command to run.
    :param single_server: boolean Run a single server or all servers.
    :param user: string Username that called the command.
    :return:
    """
    log.debug('Run Command - {0} - {1} - {2}'.format(site['sid'], single_server, command))

    # 'match' searches for strings that begin with
    if command.startswith('drush'):
        if site['type'] is not 'homepage':
            uri = BASE_URLS[ENVIRONMENT] + '/' + site['path']
        else:
            uri = BASE_URLS[ENVIRONMENT]
        # Add user prefix and URI suffix
        altered_command = 'sudo -u {0} '.format(WEBSERVER_USER) + command + ' --uri={0}'.format(uri)

    start_time = time.time()
    if single_server:
        fabric_task_result = execute(
            fabric_tasks.command_run_single, site=site, command=altered_command, warn_only=True)
    else:
        fabric_task_result = execute(
            fabric_tasks.command_run, site=site, command=altered_command, warn_only=True)

    command_time = time.time() - start_time
    log.debug('Run Command | Site - %s | Command - %s | Time - %s | Result - %s',
              site['sid'], command, time, fabric_task_result)

    logstash_payload = {'command_time': command_time,
                        'logsource': 'atlas',
                        'command': command,
                        'instance': site['sid']}
    utilities.post_to_logstash_payload(payload=logstash_payload)


    slack_title = '{0}/{1}'.format(BASE_URLS[ENVIRONMENT], site['path'])
    slack_text = 'Command - Success - {0}/{1}'.format(BASE_URLS[ENVIRONMENT], site['path'])
    slack_color = 'good'
    slack_link = '{0}/{1}'.format(BASE_URLS[ENVIRONMENT], site['path'])
    user = user

    slack_payload = {
        "text": slack_text,
        "username": 'Atlas',
        "attachments": [
            {
                "fallback": slack_text,
                "color": slack_color,
                "author_name": site['modified_by'],
                "title": slack_title,
                "fields": [
                    {
                        "title": "Command",
                        "value": altered_command,
                        "short": True
                    },
                    {
                        "title": "Command Time",
                        "value": command_time,
                        "short": True
                    },
                    {
                        "title": "Instance",
                        "value": slack_link,
                        "short": True
                    },
                    {
                        "title": "Environment",
                        "value": ENVIRONMENT,
                        "short": True
                    },
                ],
            }
        ],
    }
    if user:
        slack_payload['user'] = user

    utilities.post_to_slack_payload(slack_payload)


@celery.task
def cron(status=None):
    """
    Prepare cron tasks and send them to subtasks.
    """
    log.info('Prepare Cron | Status - %s', status)
    # Build query.
    site_query_string = ['max_results=2000']
    log.debug('Prepare Cron | Found argument')
    # Start by eliminating f5-only and legacy items.
    site_query_string.append('&where={"f5only":false,"type":"express",')
    if status:
        log.debug('Prepare Cron | Found status')
        site_query_string.append('"status":"{0}",'.format(status))
    else:
        log.debug('Prepare Cron | No status found')
        site_query_string.append('"status":{"$in":["installed","launched","locked"]},')

    site_query = ''.join(site_query_string)
    log.debug('Prepare Cron |Query after join -| %s', site_query)
    # Remove trailing comma.
    site_query = site_query.rstrip('\,')
    log.debug('Prepare Cron |Query after rstrip | %s', site_query)
    # Add closing brace.
    site_query += '}'
    log.debug('Prepare Cron |Query final | %s', site_query)

    sites = utilities.get_eve('sites', site_query)
    if not sites['_meta']['total'] == 0:
        for site in sites['_items']:
            cron_run.delay(site)


@celery.task
def cron_run(site):
    """
    Run cron

    :param site: A complete site item.
    :param command: Cron command to run.
    :return:
    """
    log.info('Run Cron | %s ', site['sid'])
    start_time = time.time()
   
    if site['type'] is not 'homepage':
        uri = BASE_URLS[ENVIRONMENT] + '/' + site['path']
    else:
        uri = BASE_URLS[ENVIRONMENT]
    command = 'sudo -u {0} drush elysia-cron run --uri={1}'.format(WEBSERVER_USER, uri)
    try:
        execute(fabric_tasks.command_run_single, site=site, command=command)
    except CronException as error:
        log.error('Run Cron | %s | Cron failed | %s', site['sid'], error)
        raise

    log.info('Run Cron | %s | Cron success', site['sid'])
    command_time = time.time() - start_time
    logstash_payload = {'command_time': command_time,
                        'logsource': 'atlas',
                        'command': command,
                        'instance': site['sid']}
    utilities.post_to_logstash_payload(payload=logstash_payload)


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
    log.debug('Pending instances | %s', sites)
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
            log.debug('Pending instances | %s has timedelta of %s. Created: %s Current: %s',
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
    log.debug('Delete all available sites| Sites - %s', sites)
    if not sites['_meta']['total'] == 0:
        for site in sites['_items']:
            log.debug('Delete all available sites| Site - %s', site)
            utilities.delete_eve('sites', site['_id'])


@celery.task
def remove_orphan_statistics():
    """
    Get a list of statistics and key them against a list of active instances.
    """
    site_query = 'where={"type":"express","f5only":false}'
    sites = utilities.get_eve('sites', site_query)
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
                log.debug('Statistic not in list | %s', statistic['_id'])
                utilities.delete_eve('statistics', statistic['_id'])


@celery.task
def take_down_installed_old_sites():
    """
    In non-prod environments, take down instances that are older than 35 days.
    """
    if ENVIRONMENT != 'production':
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
    log.debug('Old statistics time | %s', time_ago.strftime("%Y-%m-%d %H:%M:%S GMT"))
    log.debug('outdated_statistics items | %s', outdated_statistics)
    statistic_id_list = []
    if not outdated_statistics['_meta']['total'] == 0:
        for outdated_statistic in outdated_statistics['_items']:
            statistic_id_list.append(outdated_statistic['_id'])

        log.debug('statistic_id_list | %s', statistic_id_list)

        site_query = 'where={{"_id":{{"$in":{0}}}}}'.format(json.dumps(statistic_id_list))
        log.debug('Site query | %s', site_query)
        sites = utilities.get_eve('sites', site_query)
        sites_id_list = []
        if not sites['_meta']['total'] == 0:
            for site in sites['_items']:
                sites_id_list.append(site['_id'])

        slack_fallback = '{0} statistics items have not been updated in 36 hours.'.format(
            len(statistic_id_list))
        slack_link = '{0}/statistics?{1}'.format(BASE_URLS[ENVIRONMENT], site_query)
        slack_payload = {
            "text": 'Outdated Statistics',
            "username": 'Atlas',
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
