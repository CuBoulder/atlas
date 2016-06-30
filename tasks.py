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
    fabric_task = execute(fabfile.code_deploy, item=item)
    logger.debug(fabric_task)
    # Output from execute is a dict of hosts with 'None' as the value if
    # everything went well.
    if not all(value is None for value in fabric_task.values()):
        logger.debug(fabric_task.values())
        # TODO: Push notification to someone.
        return


@celery.task
def code_update(item):
    """
    Update code checkout.

    :param item: The flask request.json object.
    :return:
    """
    logger.debug('Code update - {0}'.format(item))
    fabric_task = execute(fabfile.code_update, item=item)
    logger.debug(fabric_task)
    if not all(value is None for value in fabric_task.values()):
        logger.debug(fabric_task.values())
        # TODO: Push notification to someone.
        return


@celery.task
def code_remove(item):
    """
    Remove code from the server.

    :param item: Item to be removed.
    :return:
    """
    logger.debug('Code delete - {0}'.format(item))
    fabric_task = execute(fabfile.code_remove, item=item)
    logger.debug(fabric_task)
    if not all(value is None for value in fabric_task.values()):
        logger.debug(fabric_task.values())
        # TODO: Push notification to someone.
        return


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
    fabric_task = execute(fabfile.site_provision, site=site)
    logger.debug(fabric_task)
    if not all(value is None for value in fabric_task.values()):
        logger.debug(fabric_task.values())
        # TODO: Push notification to someone.
        return
    patch_payload = {'status': 'available'}
    patch = utilities.patch_eve('sites', site['_id'], patch_payload)
    logger.debug(patch)


@celery.task
def site_update(site):
    """
    Update an instance with the given parameters.

    :param site: A single site.
    :return:
    """
    logger.debug('Site update - {0}'.format(site))
    return


@celery.task
def command_run(command):
    """
    Run the appropriate command.

    :param command:
    :return:
    """
    return True
