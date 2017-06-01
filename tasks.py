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
def instance_provision(instance):
    """
    Provision a new instance with the given parameters.

    :param instance: A single instance.
    :return:
    """
    logger.debug('Instance provision - {0}'.format(instance))
    start_time = time.time()
    # 'db_key' needs to be added here and not in Eve so that the encryption
    # works properly.
    instance['db_key'] = utilities.encrypt_string(utilities.mysql_password())
    # Set future instance status for settings file creation.
    instance['status'] = 'available'

    provision_task = execute(fabfile.instance_provision, instance=instance)

    logger.debug(provision_task)
    logger.debug(provision_task.values)

    install_task = execute(fabfile.instance_install, instance=instance)

    logger.debug(install_task)
    logger.debug(install_task.values)

    patch_payload = {'status': 'available', 'db_key': instance['db_key'], 'statistics': instance['statistics']}
    patch = utilities.patch_eve('instance', instance['_id'], patch_payload)

    profile = utilities.get_single_eve('code', instance['code']['profile'])
    profile_string = profile['meta']['name'] + '-' + profile['meta']['version']

    core = utilities.get_single_eve('code', instance['code']['core'])
    core_string = core['meta']['name'] + '-' + core['meta']['version']

    provision_time = time.time() - start_time
    logger.info('Atlas operational statistic | Instance Provision - {0} - {1} | {2} '.format(core_string, profile_string, provision_time))
    logger.debug('Instance has been provisioned\n{0}'.format(patch))

    slack_title = '{0}/{1}'.format(base_urls[environment], instance['path'])
    slack_link = '{0}/{1}'.format(base_urls[environment], instance['path'])
    attachment_text = '{0}/instance/{1}'.format(api_urls[environment], instance['_id'])
    if False not in (provision_task.values() or install_task.values()):
        slack_message = 'Instance provision - Success - {0} seconds'.format(provision_time)
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
def instance_update(instance, updates, original):
    """
    Update an instance with the given parameters.

    :param instance: A complete Instance item, including new values.
    :param updates: A partial Instance item, including only changed keys.
    :param original: Complete original Instance item.
    :return:
    """
    logger.debug('Instance update - {0}\n{1}\n\n{2}\n\n{3}'.format(instance['_id'], instance, updates, original))

    if updates.get('code'):
        logger.debug('Found code changes.')
        core_change = False
        profile_change = False
        package_change = False
        if 'core' in updates['code']:
            logger.debug('Found core change.')
            core_change = True
            execute(fabfile.instance_core_update, instance=instance)
        if 'profile' in updates['code']:
            logger.debug('Found profile change.')
            profile_change = True
            execute(fabfile.instance_profile_update, instance=instance, original=original, updates=updates)
        if 'package' in updates['code']:
            logger.debug('Found package changes.')
            package_change = True
            execute(fabfile.instance_package_update, instance=instance)
        if core_change or profile_change or package_change:
            execute(fabfile.registry_rebuild, instance=instance)
            execute(fabfile.update_database, instance=instance)
        # Email notification if we updated packages.
        if 'package' in updates['code']:
            package_name_string = ""
            for package in instance['code']['package']:
                # Append the package name and a space.
                package_name_string += utilities.get_code_name_version(package) + " "
            # Strip the trailing space off the end.
            package_name_string = package_name_string.rstrip()
            if len(package_name_string) > 0:
                subject = 'Package added - {0}/{1}'.format(base_urls[environment], instance['path'])
                message = "Requested packages have been added to {0}/{1}.\n\n{2}\n\n - Web Express Team\n\nLogin to the instance: {0}/{1}/user?destination=admin/settings/admin/bundle/list".format(base_urls[environment], instance['path'], package_name_string)
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
                # Set new status on instance record for update to settings files.
                instance['status'] = 'installed'
                execute(fabfile.update_settings_file, instance=instance)
                execute(fabfile.clear_apc)
                patch_payload = '{"status": "installed"}'
            elif updates['status'] == 'launching':
                logger.debug('Status changed to launching')
                instance['status'] = 'launched'
                execute(fabfile.update_settings_file, instance=instance)
                execute(fabfile.instance_launch, instance=instance)
                if environment is not 'local':
                    execute(fabfile.diff_f5)
                    execute(fabfile.update_f5)
                # Let fabric send patch since it is changing update group.
            elif updates['status'] == 'take_down':
                logger.debug('Status changed to take_down')
                instance['status'] = 'down'
                execute(fabfile.update_settings_file, instance=instance)
                # execute(fabfile.instance_backup, instance=instance)
                execute(fabfile.instance_take_down, instance=instance)
                patch_payload = '{"status": "down"}'
            elif updates['status'] == 'restore':
                logger.debug('Status changed to restore')
                instance['status'] = 'installed'
                execute(fabfile.update_settings_file, instance=instance)
                execute(fabfile.instance_restore, instance=instance)
                execute(fabfile.update_database, instance=instance)
                patch_payload = '{"status": "installed"}'

            if updates['status'] != 'launching':
                patch = utilities.patch_eve('instance', instance['_id'], patch_payload)
                logger.debug(patch)

    if updates.get('settings'):
        logger.debug('Found settings change.')
        if updates['settings'].get('page_cache_maximum_age') != original['settings'].get('page_cache_maximum_age'):
            logger.debug('Found page_cache_maximum_age change.')
        execute(fabfile.update_settings_file, instance=instance)

    slack_title = '{0}/{1}'.format(base_urls[environment], instance['path'])
    slack_link = '{0}/{1}'.format(base_urls[environment], instance['path'])
    if instance['pool'] == 'poolb-homepage' and instance['type'] == 'express' and instance['status'] in ['launching', 'launched']:
        slack_title = base_urls[environment]
        slack_link = base_urls[environment]
    attachment_text = '{0}/instance/{1}'.format(api_urls[environment], instance['_id'])
    slack_message = 'Instance Update - Success'
    slack_color = 'good'
    utilities.post_to_slack(
        message=slack_message,
        title=slack_title,
        link=slack_link,
        attachment_text=attachment_text,
        level=slack_color,
        user=updates['modified_by'])


@celery.task
def instance_remove(instance):
    """
    Remove site from the server.

    :param instance: Item to be removed.
    :return:
    """
    logger.debug('Instance remove\n{0}'.format(instance))
    if instance['type'] == 'express':
        # execute(fabfile.instance_backup, instance=instance)
        # Check if stats object exists first.
        if instance.get('statistics'):
            utilities.delete_eve('statistics', instance['statistics'])
        execute(fabfile.instance_remove, instance=instance)

    if environment != 'local':
        execute(fabfile.update_f5)

    slack_title = '{0}/{1}'.format(base_urls[environment], instance['path'])
    slack_message = 'Instance Remove - Success'
    slack_color = 'good'
    utilities.post_to_slack(
        message=slack_message,
        title=slack_title,
        level=slack_color,
        user=instance['modified_by'])


@celery.task
def command_prepare(item):
    """
    Prepare instances to run the appropriate command.

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
        instance_query = 'where={0}'.format(item['query'])
        instances = utilities.get_eve('instance', instance_query)
        logger.debug('Ran query\n{0}'.format(instances))
        if not instances['_meta']['total'] == 0:
            for instance in instances['_items']:
                logger.debug('Command - {0}'.format(item['command']))
                if item['command'] == 'correct_file_permissions':
                    command_wrapper.delay(execute(fabfile.correct_file_directory_permissions, instance=instance))
                    continue
                if item['command'] == 'update_settings_file':
                    logger.debug('Update instance\n{0}'.format(instance))
                    command_wrapper.delay(execute(fabfile.update_settings_file, instance=instance))
                    continue
                if item['command'] == 'update_homepage_extra_files':
                    command_wrapper.delay(execute(fabfile.update_homepage_extra_files))
                    continue
                # if item['command'] == 'instance_backup':
                #     execute(fabfile.instance_backup, instance=instance)
                #     continue
                command_run.delay(instance, item['command'], item['single_server'], item['modified_by'])
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
def command_run(instance, command, single_server, user=None):
    """
    Run the appropriate command.

    :param instance: A complete instance item.
    :param command: Command to run.
    :param single_server: boolean Run a single server or all servers.
    :param user: string Username that called the command.
    :return:
    """
    logger.debug('Run Command - {0} - {1} - {2}'.format(instance['sid'], single_server, command))
    start_time = time.time()
    if single_server:
        fabric_task_result = execute(fabfile.command_run_single, instance=instance, command=command, warn_only=True)
    else:
        fabric_task_result = execute(fabfile.command_run, instance=instance, command=command, warn_only=True)

    logger.debug('Command result - {0}'.format(fabric_task_result))
    command_time = time.time() - start_time
    logstash_payload = {'command_time': command_time,
                        'logsource': 'atlas',
                        'command': command,
                        'instance': instance['sid']
                        }
    utilities.post_to_logstash_payload(payload=logstash_payload)

    # Cron handles its own messages.
    if command != 'drush cron':
        slack_title = '{0}/{1}'.format(base_urls[environment], instance['path'])
        slack_link = '{0}/{1}'.format(base_urls[environment], instance['path'])
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
        return fabric_task_result, instance['path']


@celery.task
def cron(type=None, status=None, include_packages=None, exclude_packages=None):
    logger.debug('Cron | Status - {0} | Include - {1} | Exclude - {2}'.format(status, include_packages, exclude_packages))
    # Build query.
    instance_query_string = ['max_results=2000']
    logger.debug('Cron - found argument')
    # Start by eliminating f5 records.
    instance_query_string.append('&where={"f5only":false,')
    if type:
        logger.debug('Cron - found type')
        instance_query_string.append('"type":"{0}",'.format(type))
    if status:
        logger.debug('Cron - found status')
        instance_query_string.append('"status":"{0}",'.format(status))
    else:
        logger.debug('Cron - No status found')
        instance_query_string.append('"status":{"$in":["installed","launched"]},')
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
                instance_query_string.append('"code.package": {{"$in": {0}}},'.format(json.dumps(include_packages_ids)))
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
                instance_query_string.append('"code.package": {{"$nin": {0}}},'.format(json.dumps(exclude_packages_ids)))

    instance_query = ''.join(instance_query_string)
    logger.debug('Query after join - {0}'.format(instance_query))
    instance_query = instance_query.rstrip('\,')
    logger.debug('Query after rstrip - {0}'.format(instance_query))
    instance_query += '}'
    logger.debug('Query final - {0}'.format(instance_query))

    instances = utilities.get_eve('instance', instance_query)
    if not instances['_meta']['total'] == 0:
        for instance in instances['_items']:
            command_run.apply_async((instance, 'drush cron', True), link=check_cron_result.s())


@celery.task
def check_cron_result(payload):
    logger.debug('Check cron result')
    # Expand the list to the variables we need.
    fabric_result, instance_path = payload

    logger.debug(fabric_result)
    # The fabric_result is a dict of {hosts: result} from fabric.
    # We loop through each row and add it to a new dict if value is not
    # None.
    # This uses constructor syntax https://doughellmann.com/blog/2012/11/12/the-performance-impact-of-using-dict-instead-of-in-cpython-2-7-2/.
    errors = {k: v for k, v in fabric_result.iteritems() if v is not None}

    instance_url = '{0}/{1}'.format(base_urls[environment], instance_path)
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
def available_instances_check():
    instance_query = 'where={"status":{"$in":["pending","available"]}}'
    instances = utilities.get_eve('instance', instance_query)
    actual_instance_count = instances['_meta']['total']
    if environment == "local":
        desired_instance_count = 2
    else:
        desired_instance_count = 5
    if actual_instance_count < desired_instance_count:
        needed_instances_count = desired_instance_count - actual_instance_count
        while needed_instances_count > 0:
            payload = {
                "status": "pending",
            }
            utilities.post_eve('instance', payload)
            needed_instances_count -= 1


@celery.task
def delete_stuck_pending_instances():
    """
    Task to delete pending instances that don't install for some reason.
    """
    instance_query = 'where={"status":"pending"}'
    instances = utilities.get_eve('sites', instance_query)
    # Loop through and remove sites that are more than 30 minutes old.
    if not instances['_meta']['total'] == 0:
        for instance in instances['_items']:
            # Parse date string into structured time.
            # See https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior
            # for mask format.
            date_created = time.strptime(instance['_created'], "%Y-%m-%d %H:%M:%S %Z")
            # Get time now, Convert date_created to seconds from epoch and
            # calculate the age of the instance.
            seconds_since_creation = time.time() - time.mktime(date_created)
            logger.debug('{0} is {1} seconds old. Created: {2} Current: {3}'.format(
                instance['sid'],
                seconds_since_creation,
                time.mktime(date_created),
                time.time())
                        )
            # 15 min * 60 sec = 900 seconds
            if seconds_since_creation > 900:
                utilities.delete_eve('sites', site['_id'])


@celery.task
def delete_all_available_instances():
    """
    Get a list of available instances and delete them.
    """
    instance_query = 'where={"status":"available"}'
    instances = utilities.get_eve('instance', site_query)
    logger.debug('instances\n {0}'.format(instances))
    if not instances['_meta']['total'] == 0:
        for instance in instances['_items']:
            logger.debug('Instance\n {0}'.format(instance))
            utilities.delete_eve('instance', instance['_id'])


@celery.task
def take_down_installed_35_day_old_instances():
    if environment != 'production':
        instance_query = 'where={"status":"installed"}'
        instances = utilities.get_eve('instance', instance_query)
        # Loop through and remove instances that are more than 35 days old.
        for instance in instances['_items']:
            # Parse date string into structured time.
            # See https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior
            # for mask format.
            date_created = time.strptime(instance['_created'],
                                         "%Y-%m-%d %H:%M:%S %Z")
            # Get time now, Convert date_created to seconds from epoch and
            # calculate the age of the instance.
            seconds_since_creation = time.time() - time.mktime(date_created)
            logger.debug(
                '{0} is {1} seconds old. Created: {2} Current: {3}'.format(
                    instance['sid'],
                    seconds_since_creation,
                    time.mktime(date_created),
                    time.time())
            )
            # 35 days * 24 hrs * 60 min * 60 sec = 302400 seconds
            if seconds_since_creation > 3024000:
                # Patch the status to 'take_down'.
                payload = {'status': 'take_down'}
                utilities.patch_eve('instance', instance['_id'], payload)
