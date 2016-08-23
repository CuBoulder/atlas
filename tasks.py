"""atlas.tasks

Celery tasks for Atlas.

"""
import sys
import fabfile
import time

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
    execute(fabfile.code_deploy, item=item)


@celery.task
def code_update(updated_item, original_item):
    """
    Update code checkout.

    :param item: The flask request.json object.
    :return:
    """
    logger.debug('Code update - {0}'.format(updated_item))
    execute(fabfile.code_update, updated_item=updated_item, original_item=original_item)


@celery.task
def code_remove(item):
    """
    Remove code from the server.

    :param item: Item to be removed.
    :return:
    """
    logger.debug('Code delete - {0}'.format(item))
    execute(fabfile.code_remove, item=item)


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
    execute(fabfile.site_provision, site=site)
    patch_payload = {'status': 'available', 'db_key': site['db_key']}
    patch = utilities.patch_eve('sites', site['_id'], patch_payload)
    logger.debug('Site has been provisioned\n{0}'.format(patch))


@celery.task
def site_update(site, updates, original):
    """
    Update an instance with the given parameters.

    :param site: A complete site item, including new values.
    :param updates: A partial site item, including only changed keys.
    :param original: Complete original site item.
    :return:
    """
    logger.debug('Site update - {0}\n{1}\n\n{2}'.format(site['_id'], site, updates))

    if updates.get('code'):
        logger.debug('Found code changes.')
        if 'package' in updates['code']:
            logger.debug('Found package changes.')
            execute(fabfile.site_package_update, site=site)
            execute(fabfile.update_database, site=site)
        if updates['code'].get('core') != original['code'].get('core'):
            logger.debug('Found core change.')
            execute(fabfile.site_core_update, site=site)
            execute(fabfile.update_database, site=site)
        if updates['code'].get('profile') != original['code'].get('profile'):
            logger.debug('Found profile change.')
            execute(fabfile.site_profile_update, site=site, original=original, updates=updates)
            execute(fabfile.update_database, site=site)

    if updates.get('status'):
        logger.debug('Found status change.')
        if updates['status'] in ['installing', 'launching', 'take_down', 'restore']:
            if updates['status'] == 'installing':
                logger.debug('Status changed to installing')
                patch_payload = '{"status": "installed"}'
            elif updates['status'] == 'launching':
                logger.debug('Status changed to launching')
                execute(fabfile.site_launch, site=site)
                patch_payload = '{"status": "launched"}'
            elif updates['status'] == 'take_down':
                logger.debug('Status changed to take_down')
                execute(fabfile.site_take_down, site=site)
                patch_payload = '{"status": "down"}'
            elif updates['status'] == 'restore':
                logger.debug('Status changed to restore')
                execute(fabfile.site_restore, site=site)
                execute(fabfile.update_database, site=site)
                patch_payload = '{"status": "installed"}'

            patch = utilities.patch_eve('sites', site['_id'], patch_payload)
            logger.debug(patch)

@celery.task
def site_remove(site):
    """
    Remove site from the server.

    :param site: Item to be removed.
    :return:
    """
    logger.debug('Site delete\n{0}'.format(site))
    execute(fabfile.site_remove, site=site)

    delete = utilities.delete_eve('sites', site['_id'])
    logger.debug(delete)


@celery.task
def command_prepare(item):
    """
    Prepare sites to run the appropriate command.

    :param item: A complete command item, including new values.
    :return:
    """
    logger.debug('Prepare Command\n{0}'.format(item))
    if item['command'] == ['clear_apc']:
        execute(fabfile.clear_apc())
        return
    if item['query']:
        site_query = 'where={0}'.format(item['query'])
        sites = utilities.get_eve('sites', site_query)
        logger.debug('Ran query\n{0}'.format(sites))
        if not sites['_meta']['total'] == 0:
            for site in sites['_items']:
                if item['command'] == ['correct_file_permissions']:
                    execute(fabfile.correct_file_directory_permissions(site))
                    continue
                if item['command'] == ['update_settings_file']:
                    execute(fabfile.update_settings_file(site))
                    continue
                if item['command'] == ['update_homepage_extra_files']:
                    execute(fabfile.update_homepage_extra_files())
                    continue
                command_run(site, item['command'], item['single_server'])


@celery.task
def command_run(site, command, single_server):
    """
    Run the appropriate command.

    :param site: A complete site item.
    :param command: Command to run.
    :param single_server: boolean Run a single server or all servers.
    :return:
    """
    logger.debug('Run Command - {0} - {1}\n{2}'.format(site['sid'], single_server, command))
    if single_server:
        execute(fabfile.command_run_single, site=site, command=command)
    else:
        execute(fabfile.command_run, site=site, command=command)


@celery.task
def cron(status=None, include_packages=None, exclude_packages=None):
    logger.debug('Cron | Status - {0} | Include - {1} | Exclude - {2}'.format(status, include_packages, exclude_packages))
    # Build query.
    site_query_string = ['max_results=2000']
    logger.debug('Cron - found argument')
    site_query_string.append('&where={')
    if status:
        logger.debug('Cron - found status')
        site_query_string.append('"status":"{0}",'.format(status))
    else:
        logger.debug('Cron - No status found')
        site_query_string.append('"status":{"$in":["installed","launched"],')
    if include_packages:
        logger.debug('Cron - found include_packages')
        for package_name in include_packages:
            packages = utilities.get_code(name=package_name)
            include_packages_ids = []
            if not packages['_meta']['total'] == 0:
                for item in packages:
                    include_packages_ids.append(item['_id'])
                site_query_string.append('"code.package": {{"$in": {0}}},'.format(include_packages_ids))
    if exclude_packages:
        logger.debug('Cron - found exclude_packages')
        for package_name in exclude_packages:
            packages = utilities.get_code(name=package_name)
            exclude_packages_ids = []
            if not packages['_meta']['total'] == 0:
                for item in packages:
                    exclude_packages_ids.append(item['_id'])
                site_query_string.append('"code.package": {{"$in": {0}}},'.format(exclude_packages_ids))

    site_query = ''.join(site_query_string)
    logger.debug('Query after join - {0}'.format(site_query))
    site_query = site_query.rstrip('\,')
    logger.debug('Query after rstrip - {0}'.format(site_query))
    site_query += '}'

    sites = utilities.get_eve('sites', site_query)
    if not sites['_meta']['total'] == 0:
        for site in sites['_items']:
            command_run(site, 'drush cron', True)


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
            payload = {'status': 'delete'}
            utilities.patch_eve('sites', site['_id'], payload)


@celery.task
def delete_all_available_sites():
    """
    Get a list of available sites and delete them
    """
    site_query = 'where={"status":"available"}'
    sites = utilities.get_eve('sites', site_query)
    payload = {'status': 'delete'}
    for site in sites:
        utilities.patch_eve('sites', site['_id'], payload)


@celery.task
def take_down_installed_35_day_old_sites():
    if environment != 'prod':
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