"""atlas.tasks

Celery tasks for Atlas.

"""
import json
import logging
import sys
import time

from celery import Celery
from celery import group
from celery.utils.log import get_task_logger
from fabric.api import execute
from datetime import datetime, timedelta

import fabfile
from atlas.config import *
from atlas import utilities
from atlas import config_celery


atlas_path = '/data/code'
if atlas_path not in sys.path:
    sys.path.append(atlas_path)


# Setup a sub-logger
# Best practice is to setup sub-loggers rather than passing the main logger between different parts of the application.
# https://docs.python.org/3/library/logging.html#logging.getLogger and
# https://stackoverflow.com/questions/39863718/how-can-i-log-outside-of-main-flask-module
log = logging.getLogger('atlas.tasks')


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
    log.debug('Code deploy | %s', item)
    code_deploy_fabric_task_result = execute(fabfile.code_deploy, item=item)
    log.debug('Code Deploy | Fabric Result | %s', code_deploy_fabric_task_result)

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
    log.debug('Code | Remove | %s', item)
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
    log.debug('Instance | Provision Task | %s', instance)
    start_time = time.time()
    # 'db_key' needs to be added here and not in Eve so that the encryption
    # works properly.
    instance['db_key'] = utilities.encrypt_string(utilities.mysql_password())
    # Set future instance status for settings file creation.
    instance['status'] = 'available'

    try:
        provision_task = execute(fabfile.instance_provision, instance=instance)
        if isinstance(provision_task.get('host_string', None), BaseException):
            raise provision_task.get('host_string')
    except CeleryException as e:
        log.info('Instance | Provision failed | %s', e.message)

    log.debug('Instance | Provision Fabric task | %s', provision_task)
    log.debug('Instance | Provision Fabric task values | %s', provision_task.values)

    try:
        install_task = execute(fabfile.instance_install, instance=instance)
        if isinstance(install_task.get('host_string', None), BaseException):
            raise install_task.get('host_string')
    except CeleryException as e:
        log.info('Instance | Install failed | %s', e.message)

    log.debug('Instance | Install Fabric task | %s', install_task)
    log.debug('Instance | Install Fabric task values | %s', install_task.values)

    patch_payload = {'status': 'available',
                     'db_key': instance['db_key'], 'statistics': instance['statistics']}
    patch = utilities.patch_eve('instance', instance['_id'], patch_payload)

    profile = utilities.get_single_eve('code', instance['code']['profile'])
    profile_string = profile['meta']['name'] + '-' + profile['meta']['version']

    core = utilities.get_single_eve('code', instance['code']['core'])
    core_string = core['meta']['name'] + '-' + core['meta']['version']

    provision_time = time.time() - start_time
    log.info('Atlas operational statistic | Instance Provision | %s | %s | %s ',
                core_string, profile_string, provision_time)
    log.debug('Instance provision | Patch | %s', patch)

    slack_title = '{0}/{1}'.format(base_urls[environment], instance['sid'])
    slack_link = '{0}/{1}'.format(base_urls[environment], instance['sid'])
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
    log.debug('Instance | Update | %s | %s | %s | %s', instance['_id'], instance, updates, original)

    if updates.get('code'):
        log.debug('Found code changes.')
        core_change = False
        profile_change = False
        package_change = False
        if 'core' in updates['code']:
            log.debug('Found core change.')
            core_change = True
            execute(fabfile.instance_core_update, instance=instance)
        if 'profile' in updates['code']:
            log.debug('Found profile change.')
            profile_change = True
            execute(fabfile.instance_profile_update, instance=instance,
                    original=original, updates=updates)
        if 'package' in updates['code']:
            log.debug('Found package changes.')
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
                subject = 'Package added - {0}/{1}'.format(base_urls[environment], instance['sid'])
                message = "Requested packages have been added to {0}/{1}.\n\n{2}\n\n - Web Express Team\n\nLogin to the instance: {0}/{1}/user?destination=admin/settings/admin/bundle/list".format(base_urls[environment], instance['sid'], package_name_string)
            else:
                subject = 'Packages removed - {0}/{1}'.format(base_urls[environment], instance['sid'])
                message = "All packages have been removed from {0}/{1}.\n\n - Web Express Team.".format(base_urls[environment], instance['sid'])
            to = ['{0}@colorado.edu'.format(instance['modified_by'])]
            utilities.send_email(message=message, subject=subject, to=to)

    if updates.get('status'):
        log.debug('Found status change.')
        if updates['status'] in ['installing', 'launching', 'take_down', 'restore']:
            if updates['status'] == 'installing':
                log.debug('Status changed to installing')
                # Set new status on instance record for update to settings files.
                instance['status'] = 'installed'
                execute(fabfile.update_settings_file, instance=instance)
                execute(fabfile.clear_apc)
                patch_payload = '{"status": "installed"}'
            elif updates['status'] == 'launching':
                log.debug('Status changed to launching')
                instance['status'] = 'launched'
                execute(fabfile.update_settings_file, instance=instance)
                execute(fabfile.instance_launch, instance=instance)
                if environment is not 'local':
                    execute(fabfile.diff_f5)
                    execute(fabfile.update_f5)
                # Let fabric send patch since it is changing update group.
            elif updates['status'] == 'take_down':
                log.debug('Status changed to take_down')
                instance['status'] = 'down'
                execute(fabfile.update_settings_file, instance=instance)
                # execute(fabfile.instance_backup, instance=instance)
                execute(fabfile.instance_take_down, instance=instance)
                patch_payload = '{"status": "down"}'
            elif updates['status'] == 'restore':
                log.debug('Status changed to restore')
                instance['status'] = 'installed'
                execute(fabfile.update_settings_file, instance=instance)
                execute(fabfile.instance_restore, instance=instance)
                execute(fabfile.update_database, instance=instance)
                patch_payload = '{"status": "installed"}'

            if updates['status'] != 'launching':
                patch = utilities.patch_eve('instance', instance['_id'], patch_payload)
                log.debug(patch)

    if updates.get('settings'):
        log.debug('Found settings change.')
        if updates['settings'].get('page_cache_maximum_age') != original['settings'].get('page_cache_maximum_age'):
            log.debug('Found page_cache_maximum_age change.')
        execute(fabfile.update_settings_file, instance=instance)

    slack_title = '{0}/{1}'.format(base_urls[environment], instance['sid'])
    slack_link = '{0}/{1}'.format(base_urls[environment], instance['sid'])
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
    Remove site from the server and delete Statistic item.

    :param instance: Item to be removed.
    :return:
    """
    log.debug('Instance | Remove | %s', instance)
    if instance['type'] == 'express':
        # execute(fabfile.instance_backup, instance=instance)
        # Check if stats object exists first.
        statistics_query = 'where={{"instance":"{0}"}}'.format(instance['_id'])
        statistics = utilities.get_eve('statistics', statistics_query)
        log.debug('Statistics | %s', statistics)
        if not statistics['_meta']['total'] == 0:
            for statistic in statistics['_items']:
                utilities.delete_eve('statistics', statistic['_id'])
        execute(fabfile.instance_remove, instance=instance)
    log.debug('Instance | Remove | Success | %s', instance)

    if environment != 'local':
        execute(fabfile.update_f5)

    slack_title = '{0}/{1}'.format(base_urls[environment], instance['sid'])
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
    log.debug('Command | %s', item)
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
        log.debug('Command | Ran query | %s', instances)
        if not instances['_meta']['total'] == 0:
            for instance in instances['_items']:
                log.debug('Command | %s', item['command'])
                if item['command'] == 'correct_file_permissions':
                    command_wrapper.delay(
                        execute(fabfile.correct_file_directory_permissions, instance=instance))
                    continue
                if item['command'] == 'update_settings_file':
                    log.debug('Command | Update Settings File | %s', instance)
                    command_wrapper.delay(execute(fabfile.update_settings_file, instance=instance))
                    continue
                if item['command'] == 'update_homepage_extra_files':
                    command_wrapper.delay(execute(fabfile.update_homepage_extra_files))
                    continue
                # if item['command'] == 'instance_backup':
                #     execute(fabfile.instance_backup, instance=instance)
                #     continue
                command_run.delay(instance, item['command'],
                                  item['single_server'], item['modified_by'])
            # After all the commands run, flush APC.
            if item['command'] == 'update_settings_file':
                log.debug('Clear APC')
                command_wrapper.delay(execute(fabfile.clear_apc))


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
def command_run(instance, command, single_server, user=None):
    """
    Run the appropriate command.

    :param instance: A complete instance item.
    :param command: Command to run.
    :param single_server: boolean Run a single server or all servers.
    :param user: string Username that called the command.
    :return:
    """
    log.debug('Command | Run | %s | %s | %s', instance['sid'], single_server, command)
    start_time = time.time()
    if single_server:
        fabric_task_result = execute(fabfile.command_run_single,
                                     instance=instance, command=command, warn_only=True)
    else:
        fabric_task_result = execute(
            fabfile.command_run, instance=instance, command=command, warn_only=True)

    log.debug('Command | Result | %s', fabric_task_result)
    command_time = time.time() - start_time
    logstash_payload = {'command_time': command_time,
                        'logsource': 'atlas',
                        'command': command,
                        'instance': instance['sid']
                        }
    utilities.post_to_logstash_payload(payload=logstash_payload)

    # Cron handles its own messages.
    if command != 'drush cron':
        slack_title = '{0}/{1}'.format(base_urls[environment], instance['sid'])
        slack_link = '{0}/{1}'.format(base_urls[environment], instance['sid'])
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
        return fabric_task_result, instance['sid']


@celery.task
def cron(instance_type=None, status=None, include_packages=None, exclude_packages=None):
    log.debug('Cron | Status - %s | Include - %s | Exclude - %s',
              status, include_packages, exclude_packages)
    # Build query.
    instance_query_string = ['max_results=2000']
    log.debug('Cron | found argument')
    # Start by eliminating f5 records.
    instance_query_string.append('&where={"f5only":false,')
    if instance_type:
        log.debug('Cron | found type')
        instance_query_string.append('"type":"{0}",'.format(instance_type))
    if status:
        log.debug('Cron | found status')
        instance_query_string.append('"status":"{0}",'.format(status))
    else:
        log.debug('Cron | No status found')
        instance_query_string.append('"status":{"$in":["installed","launched"]},')
    if include_packages:
        log.debug('Cron | found include_packages')
        for package_name in include_packages:
            packages = utilities.get_code(name=package_name)
            include_packages_ids = []
            if not packages['_meta']['total'] == 0:
                for item in packages['_items']:
                    log.debug('Cron | include_packages item | %s', item)
                    include_packages_ids.append(str(item['_id']))
                log.debug('Cron | include_packages list | %s', json.dumps(include_packages_ids))
                instance_query_string.append(
                    '"code.package": {{"$in": {0}}},'.format(json.dumps(include_packages_ids)))
    if exclude_packages:
        log.debug('Cron | found exclude_packages')
        for package_name in exclude_packages:
            packages = utilities.get_code(name=package_name)
            exclude_packages_ids = []
            if not packages['_meta']['total'] == 0:
                for item in packages['_items']:
                    log.debug('Cron | exclude_packages item | %s', item)
                    exclude_packages_ids.append(str(item['_id']))
                    log.debug('Cron | exclude_packages list | %s',
                                 json.dumps(exclude_packages_ids))
                    instance_query_string.append(
                        '"code.package": {{"$nin": {0}}},'.format(json.dumps(exclude_packages_ids)))

    instance_query = ''.join(instance_query_string)
    log.debug('Query after join | %s', instance_query)
    instance_query = instance_query.rstrip('\,')
    log.debug('Query after rstrip | %s', instance_query)
    instance_query += '}'
    log.debug('Query final | %s', instance_query)

    instances = utilities.get_eve('instance', instance_query)
    if not instances['_meta']['total'] == 0:
        for instance in instances['_items']:
            command_run.apply_async((instance, 'drush cron', True), link=check_cron_result.s())


@celery.task
def check_cron_result(payload):
    log.debug('Check cron result')
    # Expand the list to the variables we need.
    fabric_result, instance_sid = payload

    log.debug(fabric_result)
    # The fabric_result is a dict of {hosts: result} from fabric.
    # We loop through each row and add it to a new dict if value is not
    # None.
    # This uses constructor syntax https://doughellmann.com/blog/2012/11/12/the-performance-impact-of-using-dict-instead-of-in-cpython-2-7-2/.
    errors = {k: v for k, v in fabric_result.iteritems() if v is not None}

    instance_url = '{0}/{1}'.format(base_urls[environment], instance_sid)
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
    instances = utilities.get_eve('instance', instance_query)
    log.debug('Pending instances | %s', instances)
    # Loop through and remove instances that are more than 30 minutes old.
    if not instances['_meta']['total'] == 0:
        for instance in instances['_items']:
            # Parse date string into structured time.
            # See https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior
            # for mask format.
            date_created = datetime.strptime(instance['_created'], "%Y-%m-%d %H:%M:%S %Z")
            # Get datetime now and calculate the age of the instance. Since our timestamp is in GMT,
            # we need to use UTC.
            time_since_creation = datetime.utcnow() - date_created
            log.debug('%s has timedelta of %s. Created: %s Current: %s',
                      instance['sid'], time_since_creation, date_created, datetime.utcnow())
            if time_since_creation > timedelta(minutes=15):
                utilities.delete_eve('instance', instance['_id'])


@celery.task
def delete_all_available_instances():
    """
    Get a list of available instances and delete them.
    """
    instance_query = 'where={"status":"available"}'
    instances = utilities.get_eve('instance', instance_query)
    log.debug('Available Instances | %s', instances)
    if not instances['_meta']['total'] == 0:
        for instance in instances['_items']:
            log.debug('Instance to remove | %s', instance)
            utilities.delete_eve('instance', instance['_id'])


@celery.task
def delete_stats_without_active_instance():
    """
    Get a list of statistics and key them against a list of active instances. Delete any that do not
    have an active instance.
    """
    instance_query = 'where={"type":"express","f5only":false}'
    instances = utilities.get_eve('instance', instance_query)
    statistics = utilities.get_eve('statistics')
    log.debug('Statistics | %s', statistics)
    log.debug('Instances | %s', instances)
    instance_id_list = []
    # Make as list of ids for easy checking.
    if not statistics['_meta']['total'] == 0:
        if not instances['_meta']['total'] == 0:
            for instance in instances['_items']:
                instance_id_list.append(instance['_id'])
                log.debug('Instance list | %s', instance_id_list)
        for statistic in statistics['_items']:
            if statistic['instance'] not in instance_id_list:
                log.debug('Statistic not in list | %s', statistic['_id'])
                utilities.delete_eve('statistics', statistic['_id'])


@celery.task
def take_down_installed_old_instances():
    if environment != 'production':
        instance_query = 'where={"status":"installed"}'
        instances = utilities.get_eve('instance', instance_query)
        # Loop through and remove instances that are more than 35 days old.
        for instance in instances['_items']:
            # Parse date string into structured time.
            # See https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior
            # for mask format.
            date_created = time.strptime(instance['_created'], "%Y-%m-%d %H:%M:%S %Z")
            # Get time now, Convert date_created to seconds from epoch and
            # calculate the age of the instance.
            seconds_since_creation = time.time() - time.mktime(date_created)
            log.debug('%s is %s seconds old. Created: %s Current: %s',
                      instance['sid'], seconds_since_creation, time.mktime(date_created),
                      time.time())
            # 35 days * 24 hrs * 60 min * 60 sec = 302400 seconds
            if seconds_since_creation > 3024000:
                # Patch the status to 'take_down'.
                payload = {'status': 'take_down'}
                utilities.patch_eve('instance', instance['_id'], payload)


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

        instance_query = 'where={{"_id":{{"$in":{0}}}}}'.format(json.dumps(statistic_id_list))
        log.debug('Instance query | %s', instance_query)
        instances = utilities.get_eve('instance', instance_query)
        instances_id_list = []
        if not instances['_meta']['total'] == 0:
            for instance in instances['_items']:
                instances_id_list.append(instance['_id'])

        slack_fallback = '{0} statistics items have not been updated in 36 hours.'.format(
            len(statistic_id_list))
        slack_link = '{0}/statistics?{1}'.format(base_urls[environment], instance_query)
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
                    "fallback": 'Instance list',
                    # A lighter red.
                    "color": '#ee9999',
                    "fields": [
                        {
                            "title": "Instance list",
                            "value": json.dumps(instances_id_list),
                            "short": False,
                            "title_link": slack_link
                        }
                    ]
                }
            ],
        }

        utilities.post_to_slack_payload(slack_payload)
