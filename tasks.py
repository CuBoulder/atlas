"""atlas.tasks

Celery tasks for Atlas.

"""
import sys
import fabfile

from celery import Celery
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
def code_update(item):
    """
    Update code checkout.

    :param item: The flask request.json object.
    :return:
    """
    logger.debug('Code update - {0}'.format(item))
    execute(fabfile.code_update, item=item)


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
    logger.debug('Site update - {0}\n{1}'.format(site['_id'], updates))

    if updates.get('code'):
        logger.debug('Found code changes')
        if 'package' in updates['code']:
            logger.debug('Have package changes')
            execute(fabfile.site_package_update, site=site)
        if updates['code'].get('core') != original['code'].get('core'):
            logger.debug('Have core change')
            execute(fabfile.site_core_update, site=site)

    # TODO: Launch
    # TODO: Take Down
    # TODO: Restore
    if updates.get('status'):
        if updates['status'] in ['launching', 'take_down', 'restore']:
            if updates['status'] == 'launching':
                execute(fabfile.site_launch, site=site)
                patch_payload = '{{"launched":"{0} GMT", "status": "launched"}}'.format(site['_updated'])
            elif updates['status'] == 'take_down':
                execute(fabfile.site_take_down, site=site)
                patch_payload = '{{"taken_down":"{0} GMT", "status": "down"}}'.format(site['_updated'])
            elif updates['status'] == 'restore':
                execute(fabfile.site_restore, site=site)
                patch_payload = '{{"taken_down": None, "status": "assigned"}}'.format(site['_updated'])

            patch = utilities.patch_eve('sites', site['_id'], patch_payload)
            logger.debug(patch)


@celery.task
def command_run(command):
    """
    Run the appropriate command.

    :param command:
    :return:
    """
    return True
