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
from atlas import config_celerybeat



path = '/data/code'
if path not in sys.path:
    sys.path.append(path)

# Setup logging
logger = get_task_logger(__name__)

# Create the Celery app object
celery = Celery('tasks')
celery.config_from_object(config_celerybeat)

# TODO: Figure out 'pickle' message on celeryd start.

@celery.task
def code_deploy(request_json):
    """
    Deploy git repositories to the appropriate places.

    :param request_json: The flask request.json object.
    :return:
    """
    logger.debug('Code deploy - {0}'.format(request_json))
    execute(fabfile.code_deploy, request=request_json)


@celery.task
def code_update(request_json):
    """
    Update code checkout.

    :param request_json: The flask request.json object.
    :return:
    """
    logger.debug('Code update - {0}'.format(request_json))
    execute(fabfile.code_update, request=request_json)


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

    :param site: A single site from Flask request.json object.
    :return:
    """
    logger.debug('Site provision - {0}'.format(site))
    site['db_key'] = utilities.encrypt_string(utilities.mysql_password())
    execute(fabfile.site_provision, site=site)


@celery.task
def command_run(request_json):
    """
    Run the appropriate command.

    :param request_json: The flask request.json object.
    :return:
    """
    return True
