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
    # 'db_key' needs to be added here and not in Eve so that the encryption
    # works properly.
    site['db_key'] = utilities.encrypt_string(utilities.mysql_password())
    # Set future site status for settings file creation.
    site['status'] = 'available'

    provision_task = execute(fabfile.site_provision, site=site)

    logger.debug(provision_task)
    logger.debug(provision_task.values)

    install_task = execute(fabfile.site_install, site=site)

    logger.debug(install_task)
    logger.debug(install_task.values)

    patch_payload = {'status': 'available', 'db_key': site['db_key'], 'statistics': site['statistics']}
    patch = utilities.patch_eve('sites', site['_id'], patch_payload)

    logger.debug('Site has been provisioned\n{0}'.format(patch))

    slack_title = '{0}/{1}'.format(base_urls[environment], site['path'])
    slack_link = '{0}/{1}'.format(base_urls[environment], site['path'])
    attachment_text = '{0}/sites/{1}'.format(api_urls[environment], site['_id'])
    if False not in (provision_task.values() or install_task.values()):
        slack_message = 'Site provision - Success'
        slack_color = 'good'
        utilities.post_to_slack(
            message=slack_message,
            title=slack_title,
            link=slack_link,
            attachment_text=attachment_text,
            level=slack_color)


@celery.task
def site_import_from_inventory(site):
    """
    Take over an instance with the given parameters.

    :param site: A single site.
    :return:
    """
    logger.debug('Site import - {0}'.format(site))
    # Decrypt and re-encrypt DB key.
    logger.debug('Original key - {0}'.format(site['db_key']))
    site['db_key'] = utilities.replace_inventory_encryption_string(site['db_key'])
    logger.debug('New key - {0}'.format(site['db_key']))

    ownership_update_task = execute(fabfile.change_files_owner, site=site)
    logger.debug(ownership_update_task)
    logger.debug(ownership_update_task.values)

    core_update_task = execute(fabfile.site_core_update, site=site)
    logger.debug(core_update_task)
    logger.debug(core_update_task.values)

    profile_update_task = execute(fabfile.site_profile_swap, site=site)
    logger.debug(profile_update_task)
    logger.debug(profile_update_task.values)

    settings_update_task = execute(fabfile.update_settings_file, site=site)
    logger.debug(settings_update_task)
    logger.debug(settings_update_task.values)

    rewrite_symlinks_task = execute(fabfile.rewrite_symlinks, site=site)
    logger.debug(rewrite_symlinks_task)
    logger.debug(rewrite_symlinks_task.values)

    rewrite_symlinks_task = execute(fabfile.registry_rebuild, site=site)
    logger.debug(rewrite_symlinks_task)
    logger.debug(rewrite_symlinks_task.values)

    database_update_task = execute(fabfile.update_database, site=site)
    logger.debug(database_update_task)
    logger.debug(database_update_task.values)

    patch_payload = {'db_key': site['db_key'], 'statistics': site['statistics']}
    patch_task = utilities.patch_eve('sites', site['_id'], patch_payload)
    logger.debug(patch_task)
    logger.debug(patch_task.values)

    logger.debug('Site has been imported\n{0}'.format(patch_task))

    slack_title = '{0}/{1}'.format(base_urls[environment], site['path'])
    slack_link = '{0}/{1}'.format(base_urls[environment], site['path'])
    attachment_text = '{0}/sites/{1}'.format(api_urls[environment], site['_id'])
    if ('Fail' not in core_update_task.values()) and ('Fail' not in profile_update_task.values()) and ('Fail' not in settings_update_task.values()) and ('Fail' not in rewrite_symlinks_task.values()) and ('Fail' not in database_update_task.values()) and ('Fail' not in patch_task.values()):
        slack_message = 'Site import - Success'
        slack_color = 'good'
        utilities.post_to_slack(
            message=slack_message,
            title=slack_title,
            link=slack_link,
            attachment_text=attachment_text,
            level=slack_color)
    else:
        slack_message = 'Site import - Failed'
        slack_color = 'danger'
        utilities.post_to_slack(
            message=slack_message,
            title=slack_title,
            link=slack_link,
            attachment_text=attachment_text,
            level=slack_color)


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
    Remove site from the server.

    :param site: Item to be removed.
    :return:
    """
    logger.debug('Site remove\n{0}'.format(site))
    if site['type'] == 'express':
        # execute(fabfile.site_backup, site=site)
        # Check if stats object exists first.
        if site.get('statistics'):
            utilities.delete_eve('statistics', site['statistics'])
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
    if single_server:
        fabric_task_result = execute(fabfile.command_run_single, site=site, command=command, warn_only=True)
    else:
        fabric_task_result = execute(fabfile.command_run, site=site, command=command, warn_only=True)

    logger.debug('Command result - {0}'.format(fabric_task_result))

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

    if errors:
        text = 'Error'
        slack_color = 'danger'
        slack_channel = 'cron-errors'
    else:
        text = 'Success'
        slack_color = 'good'
        slack_channel = 'cron'

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
def delete_stale_pending_sites():
    site_query = 'where={"status":"pending"}'
    sites = utilities.get_eve('sites', site_query)
    # Loop through and remove sites that are more than 30 minutes old.
    for site in sites['_items']:
        # Parse date string into structured time.
        # See https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior for mask format.
        date_created = time.strptime(
            site['_created'], "%Y-%m-%d %H:%M:%S %Z")
        # Get time now, Convert date_created to seconds from epoch and
        # calculate the age of the site.
        seconds_since_creation = time.time() - time.mktime(date_created)
        # 30 min * 60 sec = 1800 seconds
        if seconds_since_creation > 1800:
            utilities.delete_eve('sites', site['_id'])


@celery.task
def delete_all_available_sites():
    """
    Get a list of available sites and delete them
    """
    site_query = 'where={"status":"available"}'
    sites = utilities.get_eve('sites', site_query)
    for site in sites:
        utilities.delete_eve('sites', site['_id'])


@celery.task
def take_down_installed_35_day_old_sites():
    if environment != 'production':
        site_query = 'where={"status":"installed"}'
        sites = utilities.get_eve('sites', site_query)
        # Loop through and remove sites that are more than 35 days old.
        for site in sites['_items']:
            # Parse date string into structured time.
            # See https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior
            # for mask format.
            date_created = time.strptime(
                site['_created'], "%Y-%m-%d %H:%M:%S %Z")
            # Get time now, Convert date_created to seconds from epoch and
            # calculate the age of the site.
            seconds_since_creation = time.time() - time.mktime(date_created)
            print('{0} is {1} seconds old'.format(
                site['sid'],
                seconds_since_creation)
            )
            # 35 days * 24 hrs * 60 min * 60 sec = 302400 seconds
            if seconds_since_creation > 3024000:
                # Patch the status to 'take_down'.
                payload = {'status': 'take_down'}
                utilities.patch_eve('sites', site['_id'], payload)