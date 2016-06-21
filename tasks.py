"""atlas.tasks

Celery tasks for Atlas.

"""
import sys
import time
import re
import random

from celery import Celery
from jinja2 import Environment, PackageLoader
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
def code_deploy(request):
    """
    Deploy git repositories to the appropriate places.

    :param request: The flask request object.
    :return:
    """
    request.json["meta"]["name"],request.json["git_url"],request.json["commit_hash"],request.json["meta"]["version"],request.json["meta"]["code_type"],request.json["meta"]["is_current"]
    return True


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