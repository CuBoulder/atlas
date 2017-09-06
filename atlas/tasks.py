"""
    atlas.tasks
    ~~~~~~
    Celery tasks for Atlas.
"""
import logging
import time
import json

from celery import Celery
from fabric.api import execute
from datetime import datetime, timedelta

from atlas import fabric_tasks
from atlas import utilities
from atlas import config_celery
from atlas.config import *

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

        instance_url = '{0}/{1}'.format(base_urls[environment], site_path)
        title = 'Run Command'
        instance_link = '<' + instance_url + '|' + instance_url + '>'
        command = 'drush elysia-cron run'
        user = 'Celerybeat'

        # Only post if an error
        if errors_for_slack:
            text = 'Error'
            slack_color = 'danger'
            slack_channel = 'cron-errors'

            slack_fallback = instance_url + ' - ' + environment + ' - ' + command

            slack_payload = {
                # Channel will be overridden on local environments.
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
                                "value": environment,
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
    log.debug('Code deploy - {0}'.format(item))
    code_deploy_fabric_task_result = execute(fabric_tasks.code_deploy, item=item)
    log.debug('Code Deploy - Fabric Result\n{0}'.format(code_deploy_fabric_task_result))

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
                        "value": environment,
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
    log.debug('Code update - {0}'.format(updated_item))
    fab_task = execute(fabric_tasks.code_update, updated_item=updated_item, original_item=original_item)

    name = updated_item['meta']['name'] if updated_item['meta']['name'] else original_item['meta']['name']
    version = updated_item['meta']['version'] if updated_item['meta']['version'] else original_item['meta']['version']
    slack_title = '{0} - {1}'.format(name, version)
    if False not in fab_task.values():
        slack_message = 'Code Update - Success'
        slack_color = 'good'
        utilities.post_to_slack(
            message=slack_message,
            title=slack_title,
            level=slack_color)


@celery.task
def code_remove(item):
    """
    Remove code from the server.

    :param item: Item to be removed.
    :return:
    """
    log.debug('Code remove - {0}'.format(item))
    fab_task = execute(fabric_tasks.code_remove, item=item)

    slack_title = '{0} - {1}'.format(item['meta']['name'],
                                     item['meta']['version'])
    if False not in fab_task.values():
        slack_message = 'Code Remove - Success'
        slack_color = 'good'
        utilities.post_to_slack(
            message=slack_message,
            title=slack_title,
            level=slack_color)


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
    except:
        log.error('Site provision failed | Database creation failed')
        raise

    try:
        provision_task = execute(fabric_tasks.site_provision, site=site)
    except:
        log.error('Site provision failed | Error Message | %s', provision_task)
        raise

    log.debug('Site provision | Provision Fabric task | %s', provision_task)
    log.debug('Site provision | Provision Fabric task values | %s', provision_task.values)

    try:
        result_correct_file_dir_permissions = execute(fabric_tasks.correct_file_directory_permissions, site=site)
    except:
        log.error('Site provision failed | Error Message | %s', result_correct_file_dir_permissions)
        raise

    try:
        install_task = execute(fabric_tasks.site_install, site=site)
    except:
        log.error('Site install failed | Error Message | %s', install_task)
        raise

    log.debug('Site provision | Install Fabric task | %s', install_task)
    log.debug('Site provision | Install Fabric task values | %s', install_task.values)

    patch_payload = {'status': 'available',
                     'db_key': site['db_key'], 'statistics': site['statistics']}
    patch = utilities.patch_eve('sites', site['_id'], patch_payload)

    profile = utilities.get_single_eve('code', site['code']['profile'])
    profile_string = profile['meta']['name'] + '-' + profile['meta']['version']

    core = utilities.get_single_eve('code', site['code']['core'])
    core_string = core['meta']['name'] + '-' + core['meta']['version']

    provision_time = time.time() - start_time
    log.info('Atlas operational statistic | Site Provision | %s | %s | %s ',
                core_string, profile_string, provision_time)
    log.debug('Site provision | Patch | %s', patch)

    slack_title = '{0}/{1}'.format(base_urls[environment], site['path'])
    slack_link = '{0}/{1}'.format(base_urls[environment], site['path'])
    attachment_text = '{0}/sites/{1}'.format(api_urls[environment], site['_id'])
    if False not in (provision_task.values() or install_task.values()):
        slack_message = 'Site provision - Success - {0} seconds'.format(provision_time)
        slack_color = 'good'
        utilities.post_to_slack(
            message=slack_message,
            title=slack_title,
            link=slack_link,
            attachment_text=attachment_text,
            level=slack_color)
        logstash_payload = {'provision_time': provision_time,
                            'logsource': 'atlas'}
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
    log.debug('Site update - {0}\n{1}\n\n{2}\n\n{3}'.format(site['_id'], site, updates, original))

    if updates.get('code'):
        log.debug('Found code changes.')
        core_change = False
        profile_change = False
        package_change = False
        if 'core' in updates['code']:
            log.debug('Found core change.')
            core_change = True
            execute(fabric_tasks.site_core_update, site=site)
        if 'profile' in updates['code']:
            log.debug('Found profile change.')
            profile_change = True
            execute(fabric_tasks.site_profile_update, site=site, original=original, updates=updates)
        if 'package' in updates['code']:
            log.debug('Found package changes.')
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
                subject = 'Package added - {0}/{1}'.format(base_urls[environment], site['path'])
                message = "Requested packages have been added to {0}/{1}.\n\n{2}\n\n - Web Express Team\n\nLogin to the site: {0}/{1}/user?destination=admin/settings/admin/bundle/list".format(base_urls[environment], site['path'], package_name_string)
            else:
                subject = 'Packages removed - {0}/{1}'.format(base_urls[environment], site['path'])
                message = "All packages have been removed from {0}/{1}.\n\n - Web Express Team.".format(base_urls[environment], site['path'])
            to = ['{0}@colorado.edu'.format(site['modified_by'])]
            utilities.send_email(message=message, subject=subject, to=to)

    if updates.get('status'):
        log.debug('Found status change.')
        if updates['status'] in ['installing', 'launching', 'locked', 'take_down', 'restore']:
            if updates['status'] == 'installing':
                log.debug('Status changed to installing')
                # Set new status on site record for update to settings files.
                site['status'] = 'installed'
                execute(fabric_tasks.update_settings_file, site=site)
                execute(fabric_tasks.clear_apc)
                patch_payload = '{"status": "installed"}'
            elif updates['status'] == 'launching':
                log.debug('Status changed to launching')
                site['status'] = 'launched'
                execute(fabric_tasks.update_settings_file, site=site)
                execute(fabric_tasks.site_launch, site=site)
                if environment is not 'local':
                    execute(fabric_tasks.diff_f5)
                    execute(fabric_tasks.update_f5)
                # Let fabric send patch since it is changing update group.
            elif updates['status'] == 'locked':
                log.debug('Status changed to locked')
                execute(fabric_tasks.update_settings_file, site=site)
            elif updates['status'] == 'take_down':
                log.debug('Status changed to take_down')
                site['status'] = 'down'
                execute(fabric_tasks.update_settings_file, site=site)
                # execute(fabric_tasks.site_backup, site=site)
                execute(fabric_tasks.site_take_down, site=site)
                patch_payload = '{"status": "down"}'
            elif updates['status'] == 'restore':
                log.debug('Status changed to restore')
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

    slack_title = '{0}/{1}'.format(base_urls[environment], site['path'])
    slack_link = '{0}/{1}'.format(base_urls[environment], site['path'])
    if site['pool'] == 'poolb-homepage' and site['type'] == 'express' and site['status'] in ['launching', 'launched']:
        slack_title = base_urls[environment]
        slack_link = base_urls[environment]
    attachment_text = '{0}/sites/{1}'.format(api_urls[environment], site['_id'])
    slack_message = 'Site Update - Success'
    slack_color = 'good'
    utilities.post_to_slack(
        message=slack_message,
        title=slack_title,
        link=slack_link,
        attachment_text=attachment_text,
        level=slack_color,
        user=updates['modified_by'])


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
        except:
            log.error('Site remove failed | Database remove failed')
            raise

        execute(fabric_tasks.site_remove, site=site)

    if environment != 'local':
        execute(fabric_tasks.update_f5)

    slack_title = '{0}/{1}'.format(base_urls[environment], site['path'])
    slack_message = 'Site Remove - Success'
    slack_color = 'good'
    utilities.post_to_slack(
        message=slack_message,
        title=slack_title,
        level=slack_color,
        user=site['modified_by'])


@celery.task
def command_prepare(item):
    """
    Prepare sites to run the appropriate command.

    :param item: A complete command item, including new values.
    :return:
    """
    log.debug('Prepare Command\n{0}'.format(item))
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
        log.debug('Ran query\n{0}'.format(sites))
        if not sites['_meta']['total'] == 0:
            for site in sites['_items']:
                log.debug('Command - {0}'.format(item['command']))
                if item['command'] == 'correct_file_permissions':
                    command_wrapper.delay(execute(fabric_tasks.correct_file_directory_permissions, site=site))
                    continue
                if item['command'] == 'update_settings_file':
                    log.debug('Update site\n{0}'.format(site))
                    command_wrapper.delay(execute(fabric_tasks.update_settings_file, site=site))
                    continue
                if item['command'] == 'update_homepage_extra_files':
                    command_wrapper.delay(execute(fabric_tasks.update_homepage_extra_files))
                    continue
                # if item['command'] == 'site_backup':
                #     execute(fabric_tasks.site_backup, site=site)
                #     continue
                command_run.delay(site=site,
                                  command=item['command'],
                                  single_server=item['single_server'],
                                  user=item['modified_by'])
            # After all the commands run, flush APC.
            if item['command'] == 'update_settings_file':
                log.debug('Clear APC')
                command_wrapper.delay(execute(fabric_tasks.clear_apc))


@celery.task
def command_wrapper(fabric_command):
    """
    Wrapper to run specific commands as delegate tasks.
    :param fabric_command: Fabric command to call
    :return:
    """
    log.debug('Command wrapper')
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
    start_time = time.time()
    if single_server:
        fabric_task_result = execute(fabric_tasks.command_run_single, site=site, command=command, warn_only=True)
    else:
        fabric_task_result = execute(fabric_tasks.command_run, site=site, command=command, warn_only=True)

    log.debug('Command result - {0}'.format(fabric_task_result))
    command_time = time.time() - start_time
    logstash_payload = {'command_time': command_time,
                        'logsource': 'atlas',
                        'command': command,
                        'instance': site['sid']
                        }
    utilities.post_to_logstash_payload(payload=logstash_payload)

    # Cron handles its own messages.
    if command != 'drush elysia-cron run':
        slack_title = '{0}/{1}'.format(base_urls[environment], site['path'])
        slack_link = '{0}/{1}'.format(base_urls[environment], site['path'])
        slack_message = 'Command - Success'
        slack_color = 'good'
        attachment_text = command
        user = user

        utilities.post_to_slack(
            message=slack_message,
            title=slack_title,
            link=slack_link,
            attachment_text=attachment_text,
            level=slack_color,
            user=user)
    else:
        return fabric_task_result, site['path']


@celery.task
def cron(type=None, status=None, include_packages=None, exclude_packages=None):
    log.debug('Cron | Status - {0} | Include - {1} | Exclude - {2}'.format(status, include_packages, exclude_packages))
    # Build query.
    site_query_string = ['max_results=2000']
    log.debug('Cron - found argument')
    # Start by eliminating f5 records.
    site_query_string.append('&where={"f5only":false,')
    if type:
        log.debug('Cron - found type')
        site_query_string.append('"type":"{0}",'.format(type))
    if status:
        log.debug('Cron - found status')
        site_query_string.append('"status":"{0}",'.format(status))
    else:
        log.debug('Cron - No status found')
        site_query_string.append('"status":{"$in":["installed","launched","locked"]},')
    if include_packages:
        log.debug('Cron - found include_packages')
        for package_name in include_packages:
            packages = utilities.get_code(name=package_name)
            include_packages_ids = []
            if not packages['_meta']['total'] == 0:
                for item in packages['_items']:
                    log.debug('Cron - include_packages item \n{0}'.format(item))
                    include_packages_ids.append(str(item['_id']))
                log.debug('Cron - include_packages list \n{0}'.format(json.dumps(include_packages_ids)))
                site_query_string.append('"code.package": {{"$in": {0}}},'.format(json.dumps(include_packages_ids)))
    if exclude_packages:
        log.debug('Cron - found exclude_packages')
        for package_name in exclude_packages:
            packages = utilities.get_code(name=package_name)
            exclude_packages_ids = []
            if not packages['_meta']['total'] == 0:
                for item in packages['_items']:
                    log.debug('Cron - exclude_packages item \n{0}'.format(item))
                    exclude_packages_ids.append(str(item['_id']))
                log.debug('Cron - exclude_packages list \n{0}'.format(json.dumps(exclude_packages_ids)))
                site_query_string.append('"code.package": {{"$nin": {0}}},'.format(json.dumps(exclude_packages_ids)))

    site_query = ''.join(site_query_string)
    log.debug('Query after join - {0}'.format(site_query))
    site_query = site_query.rstrip('\,')
    log.debug('Query after rstrip - {0}'.format(site_query))
    site_query += '}'
    log.debug('Query final - {0}'.format(site_query))

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
    command = 'drush elysia-cron run'
    try:
        execute(fabric_tasks.command_run_single, site=site, command=command)
    except CronException as e:
        log.error('Run Cron | %s | Cron failed | %s', site['sid'], e)
        raise

    log.info('Run Cron | %s | Cron success', site['sid'])
    command_time = time.time() - start_time
    logstash_payload = {'command_time': command_time,
                        'logsource': 'atlas',
                        'command': command,
                        'instance': site['sid']
                        }
    utilities.post_to_logstash_payload(payload=logstash_payload)


@celery.task
def available_sites_check():
    site_query = 'where={"status":{"$in":["pending","available"]}}'
    sites = utilities.get_eve('sites', site_query)
    actual_site_count = sites['_meta']['total']
    if environment == "local":
        desired_site_count = 2
    else:
        desired_site_count = 5
    if actual_site_count < desired_site_count:
        needed_sites_count = desired_site_count - actual_site_count
        while needed_sites_count > 0:
            payload = {
                "status": "pending",
            }
            utilities.post_eve('sites', payload)
            needed_sites_count -= 1


@celery.task
def delete_stuck_pending_sites():
    """
    Task to delete pending sites that don't install for some reason.
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
            log.debug('%s has timedelta of %s. Created: %s Current: %s',
                         site['sid'],
                         time_since_creation,
                         date_created,
                         datetime.utcnow())
            if time_since_creation > timedelta(minutes=15):
                utilities.delete_eve('sites', site['_id'])


@celery.task
def delete_all_available_sites():
    """
    Get a list of available sites and delete them.
    """
    site_query = 'where={"status":"available"}'
    sites = utilities.get_eve('sites', site_query)
    log.debug('Sites\n %s', sites)
    if not sites['_meta']['total'] == 0:
        for site in sites['_items']:
            log.debug('Site\n {0}'.format(site))
            utilities.delete_eve('sites', site['_id'])


@celery.task
def delete_statistics_without_active_instance():
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
    if environment != 'production':
        site_query = 'where={"status":"installed"}'
        sites = utilities.get_eve('sites', site_query)
        # Loop through and remove sites that are more than 35 days old.
        for site in sites['_items']:
            # Parse date string into structured time.
            # See https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior
            # for mask format.
            date_created = time.strptime(site['_created'],
                                         "%Y-%m-%d %H:%M:%S %Z")
            # Get time now, Convert date_created to seconds from epoch and
            # calculate the age of the site.
            seconds_since_creation = time.time() - time.mktime(date_created)
            log.debug(
                '{0} is {1} seconds old. Created: {2} Current: {3}'.format(
                    site['sid'],
                    seconds_since_creation,
                    time.mktime(date_created),
                    time.time())
            )
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
        slack_link = '{0}/statistics?{1}'.format(base_urls[environment], site_query)
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
                            "value": environment,
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
