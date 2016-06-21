"""atlas.tasks

Celery tasks for Atlas.

"""
import sys
import fabfile
import time
import re
import random

from celery import Celery
from celery.utils.log import get_task_logger
from jinja2 import Environment, PackageLoader
from fabric.api import execute
from atlas import config_celerybeat


path = '/data/code'
if path not in sys.path:
    sys.path.append(path)

# Tell Jinja where our templates live.
env = Environment(loader=PackageLoader('atlas', 'templates'))
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

    :param request: The flask request.json object.
    :return:
    """
    logger.info('Code deploy - {0}'.format(request_json))
    execute(fabfile.code_deploy, request=request_json)


@celery.task
def site_provision(request):
    """
    Provision a new instance with the given parameters.

    :param request: The flask request object.
    :return:
    """
    return True


@celery.task
def command_run(request):
    """
    Run the appropriate command.

    :param request: The flask request object.
    :return:
    """
    return True