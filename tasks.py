"""atlas.tasks

Celery tasks for Atlas.

"""
import sys
import fabfile
import time
import json

from celery import Celery
from celery import group
from celery.utils.log import get_task_logger
from fabric.api import execute
from datetime import datetime, timedelta
from atlas.config import *
from atlas import utilities
from atlas import config_celery


path = '/data/code'
if path not in sys.path:
    sys.path.append(path)

# Setup logging
logger = get_task_logger(__name__)

# Create the Celery app object
celery = Celery('tasks')
celery.config_from_object(config_celery)


class CeleryException(Exception):
    pass


@celery.task
def code_deploy(item):
    """
    Deploy git repositories to the appropriate places.

    :param item: The flask request.json object.
    :return:
    """
    logger.debug('Code deploy - {0}'.format(item))
    code_deploy_fabric_task_result = execute(fabfile.code_deploy, item=item)
    logger.debug('Code Deploy - Fabric Result\n{0}'.format(code_deploy_fabric_task_result))

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
    logger.debug('Code update - {0}'.format(updated_item))
    fab_task = execute(fabfile.code_update, updated_item=updated_item, original_item=original_item)

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
    logger.debug('Code remove - {0}'.format(item))
    fab_task = execute(fabfile.code_remove, item=item)

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
    logger.debug('Site provision - {0}'.format(site))
    start_time = time.time()
    # 'db_key' needs to be added here and not in Eve so that the encryption
    # works properly.
    site['db_key'] = utilities.encrypt_string(utilities.mysql_password())
    # Set future site status for settings file creation.
    site['status'] = 'available'

    try:
        provision_task = execute(fabfile.site_provision, site=site)
        if isinstance(provision_task.get('host_string', None), BaseException):
            raise provision_task.get('host_string')
    except CeleryException as e:
        logger.info('Site provision failed | Error Message | %s', e.message)

    logger.debug('Site provision | Provision Fabric task | %s', provision_task)
    logger.debug('Site provision | Provision Fabric task values | %s', provision_task.values)

    try:
        install_task = execute(fabfile.site_install, site=site)
        if isinstance(install_task.get('host_string', None), BaseException):
            raise install_task.get('host_string')
    except CeleryException as e:
        logger.info('Site install failed | Error Message | %s', e.message)

    logger.debug('Site provision | Install Fabric task | %s', install_task)
    logger.debug('Site provision | Install Fabric task values | %s', install_task.values)

    patch_payload = {'status': 'available',
                     'db_key': site['db_key'], 'statistics': site['statistics']}
    patch = utilities.patch_eve('sites', site['_id'], patch_payload)

    profile = utilities.get_single_eve('code', site['code']['profile'])
    profile_string = profile['meta']['name'] + '-' + profile['meta']['version']

    core = utilities.get_single_eve('code', site['code']['core'])
    core_string = core['meta']['name'] + '-' + core['meta']['version']

    provision_time = time.time() - start_time
    logger.info('Atlas operational statistic | Site Provision | %s | %s | %s ',
                core_string, profile_string, provision_time)
    logger.debug('Site provision | Patch | %s', patch)

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
    logger.debug('Site update - {0}\n{1}\n\n{2}\n\n{3}'.format(site['_id'], site, updates, original))

    if updates.get('code'):
        logger.debug('Found code changes.')
        core_change = False
        profile_change = False
        package_change = False
        if 'core' in updates['code']:
            logger.debug('Found core change.')
            core_change = True
            execute(fabfile.site_core_update, site=site)
        if 'profile' in updates['code']:
            logger.debug('Found profile change.')
            profile_change = True
            execute(fabfile.site_profile_update, site=site, original=original, updates=updates)
        if 'package' in updates['code']:
            logger.debug('Found package changes.')
            package_change = True
            execute(fabfile.site_package_update, site=site)
        if core_change or profile_change or package_change:
            execute(fabfile.registry_rebuild, site=site)
            execute(fabfile.update_database, site=site)
        # Email notification if we updated packages.
        if 'package' in updates['code']:
            package_name_string = ""
            for package in site['code']['package']:
                # Append the package name and a space.
                package_name_string += utilities.get_code_name_version(package) + " "
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
        logger.debug('Found status change.')
        if updates['status'] in ['installing', 'launching', 'take_down', 'restore']:
            if updates['status'] == 'installing':
                logger.debug('Status changed to installing')
                # Set new status on site record for update to settings files.
                site['status'] = 'installed'
                execute(fabfile.update_settings_file, site=site)
                execute(fabfile.clear_apc)
                patch_payload = '{"status": "installed"}'
            elif updates['status'] == 'launching':
                logger.debug('Status changed to launching')
                site['status'] = 'launched'
                execute(fabfile.update_settings_file, site=site)
                execute(fabfile.site_launch, site=site)
                if environment is not 'local':
                    execute(fabfile.diff_f5)
                    execute(fabfile.update_f5)
                # Let fabric send patch since it is changing update group.
            elif updates['status'] == 'take_down':
                logger.debug('Status changed to take_down')
                site['status'] = 'down'
                execute(fabfile.update_settings_file, site=site)
                # execute(fabfile.site_backup, site=site)
                execute(fabfile.site_take_down, site=site)
                patch_payload = '{"status": "down"}'
            elif updates['status'] == 'restore':
                logger.debug('Status changed to restore')
                site['status'] = 'installed'
                execute(fabfile.update_settings_file, site=site)
                execute(fabfile.site_restore, site=site)
                execute(fabfile.update_database, site=site)
                patch_payload = '{"status": "installed"}'

            if updates['status'] != 'launching':
                patch = utilities.patch_eve('sites', site['_id'], patch_payload)
                logger.debug(patch)

    if updates.get('settings'):
        logger.debug('Found settings change.')
        if updates['settings'].get('page_cache_maximum_age') != original['settings'].get('page_cache_maximum_age'):
            logger.debug('Found page_cache_maximum_age change.')
        execute(fabfile.update_settings_file, site=site)

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
    logger.debug('Site remove | %s', site)
    if site['type'] == 'express':
        # execute(fabfile.site_backup, site=site)
        # Check if stats object exists for the site first.
        statistics_query = 'where={{"site":"{0}"}}'.format(site['_id'])
        statistics = utilities.get_eve('statistics', statistics_query)
        logger.debug('Statistics | %s', statistics)
        if not statistics['_meta']['total'] == 0:
            for statistic in statistics['_items']:
                utilities.delete_eve('statistics', statistic['_id'])
        execute(fabfile.site_remove, site=site)

    if environment != 'local':
        execute(fabfile.update_f5)

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
    logger.debug('Prepare Command\n{0}'.format(item))
    if item['command'] == 'clear_apc':
        execute(fabfile.clear_apc())
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
        logger.debug('Ran query\n{0}'.format(sites))
        if not sites['_meta']['total'] == 0:
            for site in sites['_items']:
                logger.debug('Command - {0}'.format(item['command']))
                if item['command'] == 'correct_file_permissions':
                    command_wrapper.delay(execute(fabfile.correct_file_directory_permissions, site=site))
                    continue
                if item['command'] == 'update_settings_file':
                    logger.debug('Update site\n{0}'.format(site))
                    command_wrapper.delay(execute(fabfile.update_settings_file, site=site))
                    continue
                if item['command'] == 'update_homepage_extra_files':
                    command_wrapper.delay(execute(fabfile.update_homepage_extra_files))
                    continue
                # if item['command'] == 'site_backup':
                #     execute(fabfile.site_backup, site=site)
                #     continue
                command_run.delay(site, item['command'], item['single_server'], item['modified_by'])
            # After all the commands run, flush APC.
            if item['command'] == 'update_settings_file':
                logger.debug('Clear APC')
                command_wrapper.delay(execute(fabfile.clear_apc))


@celery.task
def command_wrapper(fabric_command):
    """
    Wrapper to run specific commands as delegate tasks.
    :param fabric_command: Fabric command to call
    :return:
    """
    logger.debug('Command wrapper')
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
    logger.debug('Run Command - {0} - {1} - {2}'.format(site['sid'], single_server, command))
    start_time = time.time()
    if single_server:
        fabric_task_result = execute(fabfile.command_run_single, site=site, command=command, warn_only=True)
    else:
        fabric_task_result = execute(fabfile.command_run, site=site, command=command, warn_only=True)

    logger.debug('Command result - {0}'.format(fabric_task_result))
    command_time = time.time() - start_time
    logstash_payload = {'command_time': command_time,
                        'logsource': 'atlas',
                        'command': command,
                        'instance': site['sid']
                        }
    utilities.post_to_logstash_payload(payload=logstash_payload)

    # Cron handles its own messages.
    if command != 'drush cron':
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
    logger.debug('Cron | Status - {0} | Include - {1} | Exclude - {2}'.format(status, include_packages, exclude_packages))
    # Build query.
    site_query_string = ['max_results=2000']
    logger.debug('Cron - found argument')
    # Start by eliminating f5 records.
    site_query_string.append('&where={"f5only":false,')
    if type:
        logger.debug('Cron - found type')
        site_query_string.append('"type":"{0}",'.format(type))
    if status:
        logger.debug('Cron - found status')
        site_query_string.append('"status":"{0}",'.format(status))
    else:
        logger.debug('Cron - No status found')
        site_query_string.append('"status":{"$in":["installed","launched"]},')
    if include_packages:
        logger.debug('Cron - found include_packages')
        for package_name in include_packages:
            packages = utilities.get_code(name=package_name)
            include_packages_ids = []
            if not packages['_meta']['total'] == 0:
                for item in packages['_items']:
                    logger.debug('Cron - include_packages item \n{0}'.format(item))
                    include_packages_ids.append(str(item['_id']))
                logger.debug('Cron - include_packages list \n{0}'.format(json.dumps(include_packages_ids)))
                site_query_string.append('"code.package": {{"$in": {0}}},'.format(json.dumps(include_packages_ids)))
    if exclude_packages:
        logger.debug('Cron - found exclude_packages')
        for package_name in exclude_packages:
            packages = utilities.get_code(name=package_name)
            exclude_packages_ids = []
            if not packages['_meta']['total'] == 0:
                for item in packages['_items']:
                    logger.debug('Cron - exclude_packages item \n{0}'.format(item))
                    exclude_packages_ids.append(str(item['_id']))
                logger.debug('Cron - exclude_packages list \n{0}'.format(json.dumps(exclude_packages_ids)))
                site_query_string.append('"code.package": {{"$nin": {0}}},'.format(json.dumps(exclude_packages_ids)))

    site_query = ''.join(site_query_string)
    logger.debug('Query after join - {0}'.format(site_query))
    site_query = site_query.rstrip('\,')
    logger.debug('Query after rstrip - {0}'.format(site_query))
    site_query += '}'
    logger.debug('Query final - {0}'.format(site_query))

    sites = utilities.get_eve('sites', site_query)
    if not sites['_meta']['total'] == 0:
        for site in sites['_items']:
            command_run.apply_async((site, 'drush cron', True), link=check_cron_result.s())


@celery.task
def check_cron_result(payload):
    logger.debug('Check cron result')
    # Expand the list to the variables we need.
    fabric_result, site_path = payload

    logger.debug(fabric_result)
    # The fabric_result is a dict of {hosts: result} from fabric.
    # We loop through each row and add it to a new dict if value is not
    # None.
    # This uses constructor syntax https://doughellmann.com/blog/2012/11/12/the-performance-impact-of-using-dict-instead-of-in-cpython-2-7-2/.
    errors = {k: v for k, v in fabric_result.iteritems() if v is not None}

    instance_url = '{0}/{1}'.format(base_urls[environment], site_path)
    title = 'Run Command'
    instance_link = '<' + instance_url + '|' + instance_url + '>'
    command = 'drush cron'
    user = 'Celerybeat'

    # Only post if an error
    if errors:
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
    logger.debug('Pending instances | %s', sites)
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
            logger.debug('%s has timedelta of %s. Created: %s Current: %s',
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
    logger.debug('Sites\n %s', sites)
    if not sites['_meta']['total'] == 0:
        for site in sites['_items']:
            logger.debug('Site\n {0}'.format(site))
            utilities.delete_eve('sites', site['_id'])


@celery.task
def delete_statistics_without_active_instance():
    """
    Get a list of statistics and key them against a list of active instances.
    """
    site_query = 'where={"type":"express","f5only":false}'
    sites = utilities.get_eve('sites', site_query)
    statistics = utilities.get_eve('statistics')
    logger.debug('Statistics | %s', statistics)
    logger.debug('Sites | %s', sites)
    site_id_list = []
    # Make as list of ids for easy checking.
    if not statistics['_meta']['total'] == 0:
        if not sites['_meta']['total'] == 0:
            for site in sites['_items']:
                site_id_list.append(site['_id'])
                logger.debug('Sites list | %s', site_id_list)
        for statistic in statistics['_items']:
            if statistic['site'] not in site_id_list:
                logger.debug('Statistic not in list | %s', statistic['_id'])
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
            logger.debug(
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
    logger.debug('Old statistics time | %s', time_ago.strftime("%Y-%m-%d %H:%M:%S GMT"))
    logger.debug('outdated_statistics items | %s', outdated_statistics)
    statistic_id_list = []
    if not outdated_statistics['_meta']['total'] == 0:
        for outdated_statistic in outdated_statistics['_items']:
            statistic_id_list.append(outdated_statistic['_id'])

        logger.debug('statistic_id_list | %s', statistic_id_list)

        site_query = 'where={{"_id":{{"$in":{0}}}}}'.format(json.dumps(statistic_id_list))
        logger.debug('Site query | %s', site_query)
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
