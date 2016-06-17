"""atlas.tasks

Celery tasks for Atlas.

"""
import sys
import time
import re
import random
import logging

from celery import Celery
from jinja2 import Environment, PackageLoader
from atlas import config_celerybeat

path = '/data/code'
if path not in sys.path:
    sys.path.append(path)

# Tell Jinja where our templates live.
env = Environment(loader=PackageLoader('atlas', 'templates'))

# Create the Celery app object
celery = Celery('tasks', broker='amqp://guest@localhost//')
celery.config_from_object(config_celerybeat)

# TODO: Figure out 'pickle' message on celeryd start

@celery.task
def deploy_code(name, git_url, commit_hash, version, code_type, current):
    """
    Deploy git repositories to the appropriate places.

    :param name:
    :param git_url:
    :param commit_hash:
    :param version:
    :param code_type:
    :param current:
    :return:
    """
    return True
